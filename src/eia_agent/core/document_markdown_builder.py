"""
document_markdown_builder -- DOC-01
Generador determinista del borrador Markdown del Documento Ambiental.

Ensambla un borrador Markdown completo del Documento Ambiental (bloques A-K)
a partir del manifest DOC-00 y de los outputs técnicos ya generados.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No inventa datos.
  - No corrige outputs técnicos del pipeline.
  - No cierra gaps ni declara aptitud administrativa.
  - No genera DOCX.
  - No modifica impactos, medidas, PVA ni auditorías.
  - Genera texto solo a partir de datos realmente presentes en los JSON/MD.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eia_agent.core.document_manifest import build_document_manifest

# ---------------------------------------------------------------------------
# Constantes públicas
# ---------------------------------------------------------------------------

DOCUMENT_OUTPUT_FILENAME = "documento_ambiental_borrador.md"
DOCUMENT_BUILD_RESULT_FILENAME = "document_build_result.json"

BLOCK_ORDER: list[str] = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]

BLOCK_STATUSES: list[str] = ["GENERATED", "PARTIAL", "MISSING", "SKIPPED"]

_ADMIN_DISCLAIMER = (
    "Documento generado automaticamente a partir de outputs tecnicos. "
    "Requiere revision tecnica/juridica. "
    "No declara aptitud administrativa."
)

_PROHIBITED_PHRASES = frozenset({
    "sin afeccion",
    "apto administrativamente",
    "se descarta",
    "todos compatibles",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_read_text(path: "str | Path") -> str | None:
    """Lee un archivo de texto. Devuelve None si no existe o no es legible."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def safe_load_json(path: "str | Path") -> "dict | list | None":
    """Carga un JSON. Devuelve None si no existe, no es legible o es inválido."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def format_missing_notice(block_id: str, missing_files: list[str]) -> str:
    """Genera un aviso visible para archivos faltantes."""
    if not missing_files:
        return ""
    files_str = "\n".join(f"  - `{f}`" for f in missing_files)
    return (
        f"> **AVISO [Bloque {block_id}]:** Este bloque no puede completarse "
        f"integramente porque faltan los siguientes archivos:\n{files_str}\n"
        f"> Los datos correspondientes quedaran como PENDIENTE hasta que se "
        f"generen los outputs del pipeline tecnico."
    )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DocumentBlockBuildResult:
    """Resultado de la generación de un bloque del Documento Ambiental."""

    block_id: str
    title: str
    status: str  # GENERATED / PARTIAL / MISSING / SKIPPED
    source_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    markdown: str = ""
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "title": self.title,
            "status": self.status,
            "source_files": list(self.source_files),
            "missing_files": list(self.missing_files),
            "markdown_length": len(self.markdown),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        return (
            f"[{self.status:9}] Bloque {self.block_id} — {self.title[:50]} "
            f"({len(self.source_files)} fuentes)"
        )


@dataclass
class DocumentMarkdownBuildResult:
    """Resultado completo de la generación del borrador Markdown."""

    expediente_id: str
    output_markdown_path: "str | None" = None
    blocks: list[DocumentBlockBuildResult] = field(default_factory=list)
    generated_blocks: list[str] = field(default_factory=list)
    partial_blocks: list[str] = field(default_factory=list)
    missing_blocks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def generated_count(self) -> int:
        return len(self.generated_blocks)

    def partial_count(self) -> int:
        return len(self.partial_blocks)

    def missing_count(self) -> int:
        return len(self.missing_blocks)

    def is_complete_draft(self) -> bool:
        """True si no hay bloques MISSING (puede haber PARTIAL con advertencias)."""
        return len(self.missing_blocks) == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "output_markdown_path": self.output_markdown_path,
            "generated_count": self.generated_count(),
            "partial_count": self.partial_count(),
            "missing_count": self.missing_count(),
            "is_complete_draft": self.is_complete_draft(),
            "generated_blocks": list(self.generated_blocks),
            "partial_blocks": list(self.partial_blocks),
            "missing_blocks": list(self.missing_blocks),
            "blocks": [b.to_dict() for b in self.blocks],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        total = len(self.blocks)
        return (
            f"DOC-01 [{self.expediente_id}] "
            f"{self.generated_count()} GENERATED / "
            f"{self.partial_count()} PARTIAL / "
            f"{self.missing_count()} MISSING "
            f"de {total} bloques — "
            f"{'BORRADOR COMPLETO' if self.is_complete_draft() else 'BORRADOR INCOMPLETO'}"
        )


# ---------------------------------------------------------------------------
# Utilidades internas de extracción
# ---------------------------------------------------------------------------

def _str(v: Any, default: str = "") -> str:
    """Convierte valor a str de forma segura."""
    if v is None:
        return default
    return str(v)


def _get(data: "dict | None", *keys: str, default: Any = None) -> Any:
    """Acceso seguro anidado en un dict."""
    if not isinstance(data, dict):
        return default
    node: Any = data
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k, default)
    return node


def _list_of(data: "dict | None", key: str) -> list:
    """Extrae una lista de un dict. Nunca lanza excepción."""
    if not isinstance(data, dict):
        return []
    val = data.get(key, [])
    return val if isinstance(val, list) else []


def _block_header(block_id: str, title: str) -> str:
    return f"## Bloque {block_id} — {title}\n"


# ---------------------------------------------------------------------------
# Builders de bloque
# ---------------------------------------------------------------------------

def build_block_a(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque A — Identificacion y descripcion del proyecto."""
    exp = Path(exp_path)
    title = "Identificacion y descripcion del proyecto"
    lines: list[str] = [_block_header("A", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    # Cargar phase2_result.json (opcional)
    phase2_path = exp / "control_interno" / "phase2_result.json"
    phase2 = safe_load_json(phase2_path)
    if phase2 is not None:
        source_files.append("control_interno/phase2_result.json")

    # Cargar phase6_actions.json
    actions_path = exp / "impactos" / "phase6_actions.json"
    actions_data = safe_load_json(actions_path)
    if actions_data is not None:
        source_files.append("impactos/phase6_actions.json")
    else:
        missing_files_local = [f for f in missing_files
                               if "phase6_actions" in f or "hechos_confirmados" in f]
        if not missing_files_local:
            missing_files_local = ["impactos/phase6_actions.json"]

    # Expediente ID
    exp_id = exp.name
    scope = _get(phase2, "scope") if phase2 else None
    lines.append(f"**Expediente:** {exp_id}\n")

    # Identificacion del promotor
    promotor = _get(scope, "promotor") or _get(phase2, "promotor")
    if promotor:
        lines.append(f"**Promotor:** {_str(promotor)}\n")
    else:
        lines.append("**Promotor:** [PENDIENTE — no consta en phase2_result.json]\n")
        warnings.append("Promotor no disponible en phase2_result.json.")

    # Actividad / objeto evaluado
    actividad = _get(scope, "actividad") or _get(scope, "actividad_principal")
    if actividad:
        lines.append(f"**Actividad principal:** {_str(actividad)}\n")

    # Coordenadas / ubicacion
    coordenadas = _get(scope, "coordenadas") or _get(scope, "ubicacion")
    if coordenadas:
        if isinstance(coordenadas, dict):
            lat = coordenadas.get("latitud") or coordenadas.get("lat")
            lon = coordenadas.get("longitud") or coordenadas.get("lon")
            if lat and lon:
                lines.append(f"**Coordenadas (WGS84):** Lat {lat}, Lon {lon}\n")
        else:
            lines.append(f"**Ubicacion:** {_str(coordenadas)}\n")

    # Referencia catastral
    rc = _get(scope, "referencia_catastral") or _get(scope, "rc")
    if rc:
        lines.append(f"**Referencia catastral:** {_str(rc)}\n")

    # Modo de elaboracion
    modo = _get(scope, "modo") or _get(scope, "modo_elaboracion")
    if modo:
        lines.append(f"**Modo de elaboracion:** {_str(modo)}\n")
    else:
        lines.append("**Modo de elaboracion:** [PENDIENTE — no declarado]\n")
        warnings.append("Modo de elaboracion no declarado en phase2_result.json.")

    if phase2 is None:
        lines.append(
            "\n> **AVISO:** No se dispone de `control_interno/phase2_result.json`. "
            "La identificacion del expediente es incompleta. "
            "Ejecute la Fase 2 del pipeline para obtener el cierre del objeto evaluado.\n"
        )
        warnings.append("phase2_result.json no disponible.")

    # Acciones del proyecto
    lines.append("\n### A.1 Acciones del proyecto\n")
    if actions_data is not None:
        actions = _list_of(actions_data, "actions")
        if actions:
            for act in actions:
                act_id = _str(_get(act, "action_id"), "?")
                act_name = _str(_get(act, "name"), "[sin nombre]")
                act_desc = _str(_get(act, "description"), "")
                act_type = _str(_get(act, "action_type"), "")
                lines.append(f"- **{act_id}** — {act_name}")
                if act_type:
                    lines.append(f"  - Tipo: {act_type}")
                if act_desc:
                    lines.append(f"  - Descripcion: {act_desc}")
                lines.append("")
        else:
            lines.append("_No se han identificado acciones del proyecto todavia._\n")
            warnings.append("No hay acciones en phase6_actions.json.")
    else:
        lines.append(
            "> _No disponible: falta `impactos/phase6_actions.json`. "
            "Ejecute `phase6-actions --write`._\n"
        )
        missing_files = list(set(missing_files + ["impactos/phase6_actions.json"]))

    # Noticia de faltantes
    if missing_files:
        notice = format_missing_notice("A", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    # Estado
    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="A",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["Estado de evidencia conforme a fase2_result.json si disponible."],
    )


def build_block_b(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque B — Inventario ambiental."""
    exp = Path(exp_path)
    title = "Inventario ambiental"
    lines: list[str] = [_block_header("B", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    inv_path = exp / "inventario" / "inventory_summary.json"
    gate_path = exp / "inventario" / "phase5_gate_result.json"

    inv = safe_load_json(inv_path)
    gate = safe_load_json(gate_path)

    if inv is not None:
        source_files.append("inventario/inventory_summary.json")
    else:
        missing_files = list(set(missing_files + ["inventario/inventory_summary.json"]))

    if gate is not None:
        source_files.append("inventario/phase5_gate_result.json")
    else:
        missing_files = list(set(missing_files + ["inventario/phase5_gate_result.json"]))

    lines.append(
        "El inventario ambiental describe el estado preoperacional del medio "
        "receptor en el entorno del emplazamiento evaluado, basandose en "
        "fuentes documentales y cartografia oficial.\n"
    )
    lines.append(
        "> **NOTA METODOLOGICA:** El inventario ambiental no equivale a aptitud "
        "administrativa. La calificacion del expediente corresponde al organo "
        "ambiental competente.\n"
    )

    # Factores del inventario
    lines.append("\n### B.1 Factores ambientales evaluados\n")
    if inv is not None:
        factors = _list_of(inv, "factors")
        if factors:
            lines.append("| Factor | Nombre | Semaforo | Estado evidencia |")
            lines.append("|--------|--------|----------|-----------------|")
            for fac in factors:
                fid = _str(_get(fac, "factor_id"), "?")
                fname = _str(_get(fac, "name"), "[sin nombre]")
                semaphore = _str(_get(fac, "inventory_semaphore"), "NO_CONSTA")
                evidence = _str(_get(fac, "evidence_state"), "PENDIENTE")
                lines.append(f"| {fid} | {fname} | {semaphore} | {evidence} |")
            lines.append("")
        else:
            lines.append("_Inventario sin factores definidos todavia._\n")
            warnings.append("inventory_summary.json sin factores.")

        # Gaps principales
        all_gaps: list[dict] = []
        for fac in factors if factors else []:
            gaps = _list_of(fac, "gaps")
            for g in gaps:
                all_gaps.append(g)

        if all_gaps:
            lines.append("\n### B.2 Gaps principales del inventario\n")
            lines.append("| Codigo | Factor | Criticidad | Modo resolucion |")
            lines.append("|--------|--------|------------|----------------|")
            for g in all_gaps[:20]:  # limitar para no saturar
                gcod = _str(_get(g, "gap_id"), "?")
                gfac = _str(_get(g, "factor_id"), "?")
                gcrit = _str(_get(g, "criticality"), "?")
                gmode = _str(_get(g, "resolution_mode"), "?")
                lines.append(f"| {gcod} | {gfac} | {gcrit} | {gmode} |")
            if len(all_gaps) > 20:
                lines.append(
                    f"\n_[...] {len(all_gaps) - 20} gaps adicionales no mostrados._\n"
                )
            lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `inventario/inventory_summary.json`. "
            "Ejecute `inventory-build --write`._\n"
        )

    # Gate Fase 5
    lines.append("\n### B.3 Estado gate de Fase 5\n")
    if gate is not None:
        gate_decision = _str(_get(gate, "decision"), "NO_EVALUADO")
        gate_total = _get(gate, "total_issues", 0)
        lines.append(f"**Decision gate Fase 5:** `{gate_decision}`\n")
        lines.append(f"**Total de incidencias gate:** {gate_total}\n")
        gate_issues = _list_of(gate, "issues")
        bloqueantes = [i for i in gate_issues
                      if _get(i, "severity") in ("ERROR", "BLOQUEANTE")]
        if bloqueantes:
            lines.append(f"**Incidencias ERROR/BLOQUEANTE:** {len(bloqueantes)}\n")
            for iss in bloqueantes[:5]:
                lines.append(f"- [{_get(iss, 'severity')}] {_get(iss, 'message', '?')}")
            lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `inventario/phase5_gate_result.json`. "
            "Ejecute `inventory-gate --write`._\n"
        )

    # Fichas de inventario disponibles
    fichas_dir = exp / "inventario"
    fichas_md = list(fichas_dir.glob("FI-*.md")) if fichas_dir.is_dir() else []
    if fichas_md:
        lines.append(f"\n### B.4 Fichas de inventario disponibles ({len(fichas_md)})\n")
        for fic in sorted(fichas_md)[:16]:
            lines.append(f"- `{fic.name}`")
        lines.append("")
        source_files.append(f"inventario/ ({len(fichas_md)} fichas FI-*.md)")

    if missing_files:
        notice = format_missing_notice("B", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="B",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["Inventario no equivale a aptitud administrativa."],
    )


def build_block_c(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque C — Identificacion y valoracion de impactos."""
    exp = Path(exp_path)
    title = "Identificacion y valoracion de impactos"
    lines: list[str] = [_block_header("C", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    conesa_path = exp / "impactos" / "phase6_model_with_conesa.json"
    cumul_path = exp / "impactos" / "cumulative_synergistic_result.json"
    cumul_md_path = exp / "impactos" / "C5_acumulativos_sinergicos.md"
    audit_conesa_path = exp / "auditoria" / "conesa_check_result.json"

    conesa_data = safe_load_json(conesa_path)
    cumul_data = safe_load_json(cumul_path)
    cumul_md = safe_read_text(cumul_md_path)
    audit_conesa = safe_load_json(audit_conesa_path)

    if conesa_data is not None:
        source_files.append("impactos/phase6_model_with_conesa.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_conesa.json"]))

    if cumul_data is not None:
        source_files.append("impactos/cumulative_synergistic_result.json")
    else:
        missing_files = list(set(missing_files + ["impactos/cumulative_synergistic_result.json"]))

    if cumul_md is not None:
        source_files.append("impactos/C5_acumulativos_sinergicos.md")

    if audit_conesa is not None:
        source_files.append("auditoria/conesa_check_result.json")
    else:
        missing_files = list(set(missing_files + ["auditoria/conesa_check_result.json"]))

    lines.append(
        "La valoracion de impactos sigue la metodologia Conesa (1997, revisada). "
        "Los impactos con atributos no determinados quedan como INDETERMINADO "
        "hasta disponer de datos de campo suficientes.\n"
    )
    lines.append(
        "> **NOTA:** Los impactos INDETERMINADO no pueden cerrarse en modo "
        "gabinete sin datos adicionales. Su valoracion definitiva queda "
        "condicionada a la aportacion de datos por el promotor o al organo "
        "ambiental competente.\n"
    )

    # Impactos identificados y valorados
    lines.append("\n### C.1 Impactos identificados\n")
    if conesa_data is not None:
        impacts = _list_of(conesa_data, "impacts")
        if impacts:
            lines.append(
                "| ID | Accion | Receptor | Naturaleza | Significancia s/medidas |"
            )
            lines.append(
                "|----|--------|----------|------------|------------------------|"
            )
            for imp in impacts:
                iid = _str(_get(imp, "impact_id"), "?")
                iact = _str(_get(imp, "action_id"), "?")
                irec = _str(_get(imp, "receptor_id"), "?")
                inat = _str(_get(imp, "nature"), "?")
                isig = _str(_get(imp, "significance_without_measures"), "NO_VALORADO")
                lines.append(f"| {iid} | {iact} | {irec} | {inat} | {isig} |")
            lines.append("")

            # Indeterminados
            indets = [i for i in impacts
                     if _get(i, "significance_without_measures") == "INDETERMINADO"
                     or _get(i, "nature") == "INDETERMINADO"]
            if indets:
                lines.append(
                    f"\n**Impactos INDETERMINADO ({len(indets)}):** "
                    "Pendientes de datos adicionales para valoracion definitiva.\n"
                )
                warnings.append(
                    f"{len(indets)} impacto(s) con valoracion INDETERMINADO."
                )

            # Valoracion Conesa
            lines.append("\n### C.2 Valoracion Conesa\n")
            scored = [
                i for i in impacts
                if _get(i, "conesa_attributes") and
                any(_get(i, "conesa_attributes", a) is not None
                    for a in ["intensidad", "extension", "momento"])
            ]
            if scored:
                lines.append(
                    "| ID | Score | Clasificacion |"
                )
                lines.append("|----|-------|--------------|")
                for imp in impacts:
                    iid = _str(_get(imp, "impact_id"), "?")
                    ca = _get(imp, "conesa_attributes") or {}
                    score = _get(ca, "conesa_score")
                    classif = _get(ca, "conesa_classification")
                    if score is not None or classif is not None:
                        lines.append(
                            f"| {iid} | {_str(score, 'N/A')} | {_str(classif, 'N/A')} |"
                        )
                lines.append("")
            else:
                lines.append(
                    "_Los atributos Conesa aun no han sido puntuados o son INDETERMINADO._\n"
                )
        else:
            lines.append("_No se han identificado impactos todavia._\n")
            warnings.append("No hay impactos en phase6_model_with_conesa.json.")
    else:
        lines.append(
            "> _No disponible: falta `impactos/phase6_model_with_conesa.json`. "
            "Ejecute `phase6-assign-conesa --write`._\n"
        )

    # Auditoria Conesa
    lines.append("\n### C.3 Resultado auditoria cobertura Conesa\n")
    if audit_conesa is not None:
        ac_valid = _get(audit_conesa, "is_valid", False)
        ac_issues = _list_of(audit_conesa, "issues")
        lines.append(f"**Estado auditoria Conesa:** `{'VALIDO' if ac_valid else 'CON_INCIDENCIAS'}`\n")
        if ac_issues:
            lines.append(f"**Incidencias:** {len(ac_issues)}\n")
            errors = [i for i in ac_issues if _get(i, "severity") in ("ERROR", "BLOQUEANTE")]
            if errors:
                for err in errors[:5]:
                    lines.append(f"- [ERROR] {_get(err, 'message', '?')}")
                lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `auditoria/conesa_check_result.json`. "
            "Ejecute `audit-conesa --write`._\n"
        )

    # C.5 Acumulativos y sinergicos
    lines.append("\n### C.4 Efectos acumulativos y sinergicos (C.5)\n")
    if cumul_md is not None:
        lines.append(cumul_md)
        lines.append("")
    elif cumul_data is not None:
        cum_groups = _list_of(cumul_data, "cumulative_groups")
        syn_groups = _list_of(cumul_data, "synergistic_groups")
        lines.append(f"**Grupos acumulativos identificados:** {len(cum_groups)}\n")
        lines.append(f"**Grupos sinergeticos identificados:** {len(syn_groups)}\n")
    else:
        lines.append(
            "> _No disponible: falta `impactos/cumulative_synergistic_result.json`. "
            "Ejecute `phase6-cumulative --write`._\n"
        )

    if missing_files:
        notice = format_missing_notice("C", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="C",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["No se recalculan impactos. Solo se transcriben outputs del pipeline."],
    )


def build_block_d(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque D — Medidas preventivas, correctoras, protectoras, diagnosticas y documentales."""
    exp = Path(exp_path)
    title = "Medidas preventivas, correctoras, protectoras, diagnosticas y documentales"
    lines: list[str] = [_block_header("D", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    meas_path = exp / "impactos" / "phase6_model_with_measures.json"
    diag_path = exp / "auditoria" / "diagnostic_measure_validation_result.json"
    prl_path = exp / "auditoria" / "prl_measure_validation_result.json"

    meas_data = safe_load_json(meas_path)
    diag_data = safe_load_json(diag_path)
    prl_data = safe_load_json(prl_path)

    if meas_data is not None:
        source_files.append("impactos/phase6_model_with_measures.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_measures.json"]))

    if diag_data is not None:
        source_files.append("auditoria/diagnostic_measure_validation_result.json")
    else:
        missing_files = list(
            set(missing_files + ["auditoria/diagnostic_measure_validation_result.json"])
        )

    if prl_data is not None:
        source_files.append("auditoria/prl_measure_validation_result.json")
    else:
        missing_files = list(
            set(missing_files + ["auditoria/prl_measure_validation_result.json"])
        )

    lines.append(
        "Las medidas ambientales se clasifican por tipo segun su caracter: "
        "preventivas, correctoras, protectoras, diagnosticas y documentales. "
        "Las medidas PRL se listan separadas.\n"
    )
    lines.append(
        "> **AVISO METODOLOGICO:** Las medidas diagnosticas y las medidas PRL "
        "no reducen por si mismas la significancia ambiental del impacto. "
        "Solo las medidas preventivas, correctoras y protectoras pueden "
        "mejorar la significancia residual.\n"
    )

    if meas_data is not None:
        measures = _list_of(meas_data, "measures")

        def _filter_measures(measures: list, **kwargs: Any) -> list:
            result = []
            for m in measures:
                match = all(
                    _get(m, k) == v for k, v in kwargs.items()
                )
                if match:
                    result.append(m)
            return result

        def _render_measures_table(category: str, mlist: list) -> list[str]:
            sub: list[str] = []
            sub.append(f"\n### D.{category} Medidas {category.lower()}\n")
            if mlist:
                sub.append("| ID | Nombre | Tipo | Estado |")
                sub.append("|----|--------|------|--------|")
                for m in mlist:
                    mid = _str(_get(m, "measure_id"), "?")
                    mname = _str(_get(m, "name"), "[sin nombre]")
                    mtype = _str(_get(m, "measure_type"), "?")
                    mst = _str(_get(m, "status"), "PROPUESTA")
                    sub.append(f"| {mid} | {mname} | {mtype} | {mst} |")
                sub.append("")
            else:
                sub.append(f"_No hay medidas {category.lower()} identificadas._\n")
            return sub

        # Separar por tipo
        preventivas = [m for m in measures
                      if _get(m, "measure_type") == "PREVENTIVA"
                      and not _get(m, "is_diagnostic") and not _get(m, "is_prl_only")]
        correctoras = [m for m in measures
                      if _get(m, "measure_type") == "CORRECTORA"
                      and not _get(m, "is_diagnostic") and not _get(m, "is_prl_only")]
        protectoras = [m for m in measures
                      if _get(m, "measure_type") == "PROTECTORA"
                      and not _get(m, "is_diagnostic") and not _get(m, "is_prl_only")]
        diagnosticas = [m for m in measures if _get(m, "is_diagnostic")]
        prl_measures = [m for m in measures if _get(m, "is_prl_only")]
        documentales = [m for m in measures
                       if _get(m, "measure_type") == "DOCUMENTAL"
                       and not _get(m, "is_diagnostic") and not _get(m, "is_prl_only")]

        lines.extend(_render_measures_table("Preventivas", preventivas))
        lines.extend(_render_measures_table("Correctoras", correctoras))
        lines.extend(_render_measures_table("Protectoras", protectoras))
        lines.extend(_render_measures_table("Diagnosticas", diagnosticas))
        lines.extend(_render_measures_table("Documentales", documentales))

        if prl_measures:
            lines.append("\n### D.PRL Medidas de Prevencion de Riesgos Laborales (no EIA)\n")
            lines.append(
                "> **AVISO:** Estas medidas pertenecen al marco legal de PRL "
                "(Ley 31/1995 y normativa derivada). No son medidas EIA y "
                "no reducen la significancia ambiental del impacto.\n"
            )
            lines.append("| ID | Nombre | Estado |")
            lines.append("|----|--------|--------|")
            for m in prl_measures:
                mid = _str(_get(m, "measure_id"), "?")
                mname = _str(_get(m, "name"), "[sin nombre]")
                mst = _str(_get(m, "status"), "PROPUESTA")
                lines.append(f"| {mid} | {mname} | {mst} |")
            lines.append("")

        if not measures:
            lines.append("_No se han generado medidas todavia._\n")
            warnings.append("No hay medidas en phase6_model_with_measures.json.")
    else:
        lines.append(
            "> _No disponible: falta `impactos/phase6_model_with_measures.json`. "
            "Ejecute `phase6-generate-measures --write`._\n"
        )

    # Auditoria diagnostica
    if diag_data is not None:
        dv = _get(diag_data, "is_valid", True)
        di = _list_of(diag_data, "issues")
        lines.append("\n### D.Auditoria Medidas diagnosticas\n")
        lines.append(f"**Estado:** `{'VALIDO' if dv else 'CON_INCIDENCIAS'}`\n")
        if di:
            lines.append(f"**Incidencias:** {len(di)}\n")
    else:
        lines.append(
            "\n> _Auditoria diagnostica no disponible (falta "
            "`auditoria/diagnostic_measure_validation_result.json`)._\n"
        )

    # Auditoria PRL
    if prl_data is not None:
        pv = _get(prl_data, "is_valid", True)
        pi = _list_of(prl_data, "issues")
        lines.append("\n### D.Auditoria Separacion EIA/PRL\n")
        lines.append(f"**Estado:** `{'VALIDO' if pv else 'CON_INCIDENCIAS'}`\n")
        if pi:
            lines.append(f"**Incidencias:** {len(pi)}\n")
    else:
        lines.append(
            "\n> _Auditoria PRL no disponible (falta "
            "`auditoria/prl_measure_validation_result.json`)._\n"
        )

    if missing_files:
        notice = format_missing_notice("D", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="D",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=[
            "Medidas diagnosticas y PRL no reducen significancia ambiental.",
            "No se modifican medidas existentes.",
        ],
    )


def build_block_e(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque E — Programa de vigilancia ambiental."""
    exp = Path(exp_path)
    title = "Programa de vigilancia ambiental"
    lines: list[str] = [_block_header("E", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    pva_path = exp / "impactos" / "phase6_model_with_pva.json"
    cov_path = exp / "impactos" / "pva_coverage_result.json"
    cov_md_path = exp / "impactos" / "pva_coverage_result.md"

    pva_data = safe_load_json(pva_path)
    cov_data = safe_load_json(cov_path)
    cov_md = safe_read_text(cov_md_path)

    if pva_data is not None:
        source_files.append("impactos/phase6_model_with_pva.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_pva.json"]))

    if cov_data is not None:
        source_files.append("impactos/pva_coverage_result.json")
    else:
        missing_files = list(set(missing_files + ["impactos/pva_coverage_result.json"]))

    if cov_md is not None:
        source_files.append("impactos/pva_coverage_result.md")

    lines.append(
        "El Programa de Vigilancia Ambiental (PVA) establece los indicadores, "
        "frecuencias de seguimiento y responsables para cada impacto relevante. "
        "Se estructura mediante fichas por receptor ambiental afectado.\n"
    )

    # Fichas PVA
    lines.append("\n### E.1 Fichas del PVA\n")
    if pva_data is not None:
        pva_programs = _list_of(pva_data, "pva_programs")
        if pva_programs:
            lines.append("| ID PVA | Nombre | Factor | Frecuencia | Estado |")
            lines.append("|--------|--------|--------|------------|--------|")
            for pva in pva_programs:
                pvaid = _str(_get(pva, "pva_id"), "?")
                pvaname = _str(_get(pva, "name"), "[sin nombre]")
                pvafac = _str(_get(pva, "receptor_id") or _get(pva, "factor_id"), "?")
                pvafq = _str(_get(pva, "frequency") or _get(pva, "monitoring_frequency"), "?")
                pvast = _str(_get(pva, "status"), "PROPUESTO")
                lines.append(f"| {pvaid} | {pvaname} | {pvafac} | {pvafq} | {pvast} |")
            lines.append("")

            # Condicionados
            conditioned = [p for p in pva_programs if _get(p, "conditioned")]
            if conditioned:
                lines.append(
                    f"\n**PVA condicionados:** {len(conditioned)} ficha(s) estan "
                    "condicionadas a la resolucion de contradicciones o gaps previos.\n"
                )
                warnings.append(
                    f"{len(conditioned)} fichas PVA condicionadas a resolucion de CONTs/gaps."
                )
        else:
            lines.append("_No hay fichas PVA generadas todavia._\n")
            warnings.append("No hay fichas PVA en phase6_model_with_pva.json.")
    else:
        lines.append(
            "> _No disponible: falta `impactos/phase6_model_with_pva.json`. "
            "Ejecute `phase6-generate-pva --write`._\n"
        )

    # Cobertura PVA
    lines.append("\n### E.2 Cobertura PVA\n")
    if cov_md is not None:
        lines.append(cov_md)
        lines.append("")
    elif cov_data is not None:
        covered = _get(cov_data, "covered_count", 0)
        uncovered = _get(cov_data, "uncovered_count", 0)
        valid = _get(cov_data, "is_valid", False)
        lines.append(f"**Impactos con cobertura PVA:** {covered}\n")
        lines.append(f"**Impactos sin cobertura PVA:** {uncovered}\n")
        lines.append(f"**Estado:** `{'VALIDO' if valid else 'CON_GAPS'}`\n")
        if uncovered:
            warnings.append(f"{uncovered} impacto(s) sin cobertura PVA.")
    else:
        lines.append(
            "> _No disponible: falta `impactos/pva_coverage_result.json`. "
            "Ejecute `phase6-validate-pva --write`._\n"
        )

    if missing_files:
        notice = format_missing_notice("E", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="E",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["No se modifican fichas PVA existentes."],
    )


def build_block_f(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque F — Vulnerabilidad ante riesgos y catastrofes."""
    exp = Path(exp_path)
    title = "Vulnerabilidad ante riesgos y catastrofes"
    lines: list[str] = [_block_header("F", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    inv_path = exp / "inventario" / "inventory_summary.json"
    conesa_path = exp / "impactos" / "phase6_model_with_conesa.json"

    inv = safe_load_json(inv_path)
    conesa_data = safe_load_json(conesa_path)

    if inv is not None:
        source_files.append("inventario/inventory_summary.json")
    else:
        missing_files = list(set(missing_files + ["inventario/inventory_summary.json"]))

    if conesa_data is not None:
        source_files.append("impactos/phase6_model_with_conesa.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_conesa.json"]))

    lines.append(
        "Este bloque analiza la vulnerabilidad del proyecto y del entorno "
        "ante riesgos naturales y catastrofes, incluyendo inundabilidad, "
        "riesgos sismicos, incendios forestales y cambio climatico.\n"
    )
    lines.append(
        "> **CAUTELA:** La evaluacion de vulnerabilidad no puede cerrarse en "
        "modo gabinete sin datos cartograficos oficiales verificados. "
        "Los datos presentados tienen caracter estimado o provisional.\n"
    )

    # FI-016 Riesgos naturales
    lines.append("\n### F.1 Riesgos naturales (FI-016)\n")
    if inv is not None:
        factors = _list_of(inv, "factors")
        fi016 = next((f for f in factors if _get(f, "factor_id") == "FI-016"), None)
        fi005 = next((f for f in factors if _get(f, "factor_id") == "FI-005"), None)

        if fi016:
            fi016_sem = _str(_get(fi016, "inventory_semaphore"), "NO_CONSTA")
            fi016_ev = _str(_get(fi016, "evidence_state"), "PENDIENTE")
            lines.append(f"**Estado FI-016 (Riesgos naturales):** {fi016_sem} | {fi016_ev}\n")
            fi016_gaps = _list_of(fi016, "gaps")
            if fi016_gaps:
                lines.append(
                    f"**Gaps activos FI-016:** {len(fi016_gaps)} "
                    "(requieren datos adicionales)\n"
                )
                warnings.append(f"FI-016 tiene {len(fi016_gaps)} gaps activos.")
        else:
            lines.append("_FI-016 (Riesgos naturales) no encontrado en inventory_summary.json._\n")
            warnings.append("FI-016 no disponible en inventario.")

        if fi005:
            fi005_sem = _str(_get(fi005, "inventory_semaphore"), "NO_CONSTA")
            fi005_ev = _str(_get(fi005, "evidence_state"), "PENDIENTE")
            lines.append(f"\n**Estado FI-005 (Inundabilidad):** {fi005_sem} | {fi005_ev}\n")
            fi005_gaps = _list_of(fi005, "gaps")
            if fi005_gaps:
                lines.append(
                    f"**Gaps activos FI-005:** {len(fi005_gaps)}\n"
                )
    else:
        lines.append(
            "> _No disponible: falta `inventario/inventory_summary.json`._\n"
        )

    # Cambio climatico
    lines.append("\n### F.2 Cambio climatico y vulnerabilidad futura\n")
    if inv is not None:
        factors = _list_of(inv, "factors")
        fi015 = next((f for f in factors if _get(f, "factor_id") == "FI-015"), None)
        if fi015:
            fi015_sem = _str(_get(fi015, "inventory_semaphore"), "NO_CONSTA")
            lines.append(
                f"**FI-015 (Cambio climatico):** {fi015_sem}\n"
            )
        else:
            lines.append(
                "_FI-015 (Cambio climatico) no encontrado en inventory_summary.json._\n"
            )
    else:
        lines.append("> _Datos no disponibles._\n")

    # Impactos relacionados con riesgos en el modelo Conesa
    lines.append("\n### F.3 Impactos sobre riesgo en el modelo\n")
    if conesa_data is not None:
        impacts = _list_of(conesa_data, "impacts")
        risk_impacts = [
            i for i in impacts
            if "FR-016" in _str(_get(i, "receptor_id")) or
               "FR-005" in _str(_get(i, "receptor_id")) or
               "riesgo" in _str(_get(i, "name")).lower()
        ]
        if risk_impacts:
            for ri in risk_impacts:
                lines.append(
                    f"- {_get(ri, 'impact_id')}: {_get(ri, 'name')} "
                    f"| Significancia: {_get(ri, 'significance_without_measures', 'NO_VALORADO')}"
                )
            lines.append("")
        else:
            lines.append(
                "_No se han identificado impactos especificos sobre riesgos naturales._\n"
            )
    else:
        lines.append("> _Datos de impactos no disponibles._\n")

    if missing_files:
        notice = format_missing_notice("F", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="F",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["Evaluacion de vulnerabilidad en modo gabinete es siempre estimada."],
    )


def build_block_g(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque G — Alternativas y justificacion de solucion adoptada."""
    exp = Path(exp_path)
    title = "Alternativas y justificacion de solucion adoptada"
    lines: list[str] = [_block_header("G", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    phase3_path = exp / "control_interno" / "phase3_result.json"
    phase3 = safe_load_json(phase3_path)

    if phase3 is not None:
        source_files.append("control_interno/phase3_result.json")

    # Nota: capas/hechos_confirmados.json y capas/normativa_aplicable.json
    # son inputs del manifest pero alternativas vienen de phase3 si existe
    hechos_path = exp / "capas" / "hechos_confirmados.json"
    hechos = safe_load_json(hechos_path)
    if hechos is not None:
        source_files.append("capas/hechos_confirmados.json")

    normativa_path = exp / "capas" / "normativa_aplicable.json"
    normativa = safe_load_json(normativa_path)
    if normativa is not None:
        source_files.append("capas/normativa_aplicable.json")

    lines.append(
        "La evaluacion de alternativas analiza las opciones tecnicas y de "
        "localizacion consideradas por el promotor, justificando la solucion "
        "finalmente adoptada.\n"
    )
    lines.append(
        "> **AVISO:** Si el promotor no ha aportado documentacion de alternativas, "
        "este bloque no puede completarse con datos confirmados. "
        "Los datos presentados tienen caracter declarado o estimado.\n"
    )

    if phase3 is not None:
        proc = _get(phase3, "procedure") or {}
        proc_type = _str(_get(proc, "type") or _get(proc, "procedure_type"), "NO_DETERMINADO")
        lines.append(f"\n**Procedimiento normativo determinado:** {proc_type}\n")

        cautelas = _list_of(phase3, "cautelas") or _list_of(phase3, "warnings")
        if cautelas:
            lines.append("\n**Cautelas identificadas en triaje normativo:**\n")
            for c in cautelas[:10]:
                if isinstance(c, str):
                    lines.append(f"- {c}")
                elif isinstance(c, dict):
                    lines.append(f"- {_get(c, 'message', _str(c))}")
            lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `control_interno/phase3_result.json`. "
            "Ejecute `phase3 --write`._\n"
        )

    # Alternativas
    lines.append("\n### G.1 Alternativas consideradas\n")
    if phase3 is not None:
        alternativas = _list_of(phase3, "alternativas") or _list_of(phase3, "alternatives")
        if alternativas:
            for i, alt in enumerate(alternativas, 1):
                aname = _str(_get(alt, "name") or _get(alt, "nombre"), f"Alternativa {i}")
                adesc = _str(_get(alt, "description") or _get(alt, "descripcion"), "")
                lines.append(f"**{aname}:** {adesc}\n")
        else:
            lines.append(
                "> _No consta documentacion de alternativas en phase3_result.json. "
                "Este bloque queda PARTIAL hasta que el promotor aporte la justificacion "
                "de la solucion adoptada._\n"
            )
            warnings.append(
                "No constan alternativas en phase3_result.json. "
                "Bloque G marcado PARTIAL."
            )
    else:
        lines.append(
            "> _No constan alternativas en los outputs disponibles. "
            "Este bloque queda PARTIAL hasta que el promotor aporte "
            "documentacion de alternativas._\n"
        )
        warnings.append("No hay datos de alternativas disponibles.")

    lines.append("\n### G.2 Justificacion de la solucion adoptada\n")
    lines.append(
        "_[Requiere aportacion del promotor o datos de la Fase 2 que incluyan "
        "la justificacion de la alternativa seleccionada.]_\n"
    )
    warnings.append(
        "Justificacion de solucion adoptada pendiente de datos del promotor."
    )

    if missing_files:
        notice = format_missing_notice("G", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    # G es PARTIAL si no hay datos de alternativas (es un bloque tipicamente incompleto
    # en modo gabinete)
    if not source_files:
        status = "MISSING"
    else:
        # Siempre PARTIAL en modo gabinete a menos que haya datos de alternativas confirmados
        status = "PARTIAL"

    return DocumentBlockBuildResult(
        block_id="G",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=[
            "Alternativas no inventadas si no constan en documentacion.",
            "Bloque tipicamente PARTIAL en modo gabinete.",
        ],
    )


def build_block_h(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque H — Red Natura 2000 y espacios naturales protegidos."""
    exp = Path(exp_path)
    title = "Red Natura 2000 y espacios naturales protegidos"
    lines: list[str] = [_block_header("H", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    inv_path = exp / "inventario" / "inventory_summary.json"
    conesa_path = exp / "impactos" / "phase6_model_with_conesa.json"
    consistency_path = exp / "auditoria" / "block_consistency_result.json"

    inv = safe_load_json(inv_path)
    conesa_data = safe_load_json(conesa_path)
    consistency = safe_load_json(consistency_path)

    if inv is not None:
        source_files.append("inventario/inventory_summary.json")
    else:
        missing_files = list(set(missing_files + ["inventario/inventory_summary.json"]))

    if conesa_data is not None:
        source_files.append("impactos/phase6_model_with_conesa.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_conesa.json"]))

    if consistency is not None:
        source_files.append("auditoria/block_consistency_result.json")
    else:
        missing_files = list(
            set(missing_files + ["auditoria/block_consistency_result.json"])
        )

    lines.append(
        "Este bloque analiza la presencia de Red Natura 2000 y espacios "
        "naturales protegidos en el ambito de estudio y la posible afeccion "
        "del proyecto sobre ellos.\n"
    )
    lines.append(
        "> **CAUTELA METODOLOGICA:** La afeccion a Red Natura 2000 no puede "
        "cerrarse en modo gabinete sin cartografia oficial verificada y "
        "estudio especifico de repercusiones. "
        "No se afirma ni descarta afeccion sin datos suficientes. "
        "Usar 'no se detecta en las fuentes consultadas' en lugar de "
        "'no existe afeccion'.\n"
    )

    # FI-009 ENP y FI-010 Red Natura
    lines.append("\n### H.1 Espacios protegidos en el inventario\n")
    if inv is not None:
        factors = _list_of(inv, "factors")
        fi009 = next((f for f in factors if _get(f, "factor_id") == "FI-009"), None)
        fi010 = next((f for f in factors if _get(f, "factor_id") == "FI-010"), None)

        if fi009:
            fi009_sem = _str(_get(fi009, "inventory_semaphore"), "NO_CONSTA")
            fi009_ev = _str(_get(fi009, "evidence_state"), "PENDIENTE")
            lines.append(f"**FI-009 (ENP):** {fi009_sem} | {fi009_ev}\n")
            fi009_gaps = _list_of(fi009, "gaps")
            if fi009_gaps:
                lines.append(
                    f"**Gaps FI-009:** {len(fi009_gaps)} (requieren datos oficiales)\n"
                )
                warnings.append(f"FI-009 (ENP) tiene {len(fi009_gaps)} gaps activos.")
        else:
            lines.append(
                "_FI-009 (ENP) no encontrado en inventory_summary.json._\n"
            )
            warnings.append("FI-009 no disponible en inventario.")

        if fi010:
            fi010_sem = _str(_get(fi010, "inventory_semaphore"), "NO_CONSTA")
            fi010_ev = _str(_get(fi010, "evidence_state"), "PENDIENTE")
            lines.append(f"\n**FI-010 (Red Natura 2000):** {fi010_sem} | {fi010_ev}\n")
            fi010_gaps = _list_of(fi010, "gaps")
            if fi010_gaps:
                lines.append(
                    f"**Gaps FI-010:** {len(fi010_gaps)} (requieren datos oficiales)\n"
                )
                warnings.append(f"FI-010 (Red Natura) tiene {len(fi010_gaps)} gaps activos.")
        else:
            lines.append(
                "_FI-010 (Red Natura 2000) no encontrado en inventory_summary.json._\n"
            )
            warnings.append("FI-010 no disponible en inventario.")
    else:
        lines.append(
            "> _No disponible: falta `inventario/inventory_summary.json`._\n"
        )

    # Impactos sobre ENP/Red Natura en modelo Conesa
    lines.append("\n### H.2 Impactos identificados sobre ENP/Red Natura\n")
    if conesa_data is not None:
        impacts = _list_of(conesa_data, "impacts")
        enp_impacts = [
            i for i in impacts
            if "FR-009" in _str(_get(i, "receptor_id")) or
               "FR-010" in _str(_get(i, "receptor_id")) or
               "natura" in _str(_get(i, "name")).lower() or
               "enp" in _str(_get(i, "name")).lower()
        ]
        if enp_impacts:
            lines.append("| ID | Nombre | Significancia | Estado |")
            lines.append("|----|--------|--------------|--------|")
            for imp in enp_impacts:
                iid = _str(_get(imp, "impact_id"), "?")
                iname = _str(_get(imp, "name"), "?")
                isig = _str(_get(imp, "significance_without_measures"), "NO_VALORADO")
                ist = _str(_get(imp, "status"), "?")
                lines.append(f"| {iid} | {iname} | {isig} | {ist} |")
            lines.append("")
        else:
            lines.append(
                "_No se han identificado impactos especificos sobre ENP/Red Natura "
                "en las fuentes consultadas. "
                "Esta ausencia de registro no descarta la presencia de afeccion._\n"
            )
    else:
        lines.append("> _Datos de impactos no disponibles._\n")

    # Coherencia entre bloques
    lines.append("\n### H.3 Coherencia entre bloques\n")
    if consistency is not None:
        cons_valid = _get(consistency, "is_valid", False)
        cons_issues = _list_of(consistency, "issues")
        lines.append(
            f"**Estado coherencia:** `{'VALIDO' if cons_valid else 'CON_INCIDENCIAS'}`\n"
        )
        rn_issues = [
            i for i in cons_issues
            if "RN" in _str(_get(i, "code")) or
               "natura" in _str(_get(i, "message")).lower()
        ]
        if rn_issues:
            lines.append(
                f"**Incidencias coherencia Red Natura:** {len(rn_issues)}\n"
            )
            for ri in rn_issues[:3]:
                lines.append(f"- [{_get(ri, 'code')}] {_get(ri, 'message', '?')}")
            lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `auditoria/block_consistency_result.json`. "
            "Ejecute `audit-block-consistency --write`._\n"
        )

    if missing_files:
        notice = format_missing_notice("H", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="H",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=[
            "No se cierra afeccion a Red Natura si hay gaps activos.",
            "Evaluacion de repercusiones es competencia del organo ambiental.",
        ],
    )


def build_block_i(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque I — Conclusiones tecnicas."""
    exp = Path(exp_path)
    title = "Conclusiones tecnicas"
    lines: list[str] = [_block_header("I", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    audit_path = exp / "auditoria" / "final_audit_result.json"
    cumul_path = exp / "impactos" / "cumulative_synergistic_result.json"

    audit = safe_load_json(audit_path)
    cumul = safe_load_json(cumul_path)

    if audit is not None:
        source_files.append("auditoria/final_audit_result.json")
    else:
        missing_files = list(set(missing_files + ["auditoria/final_audit_result.json"]))

    if cumul is not None:
        source_files.append("impactos/cumulative_synergistic_result.json")
    else:
        missing_files = list(
            set(missing_files + ["impactos/cumulative_synergistic_result.json"])
        )

    lines.append(
        "Las conclusiones tecnicas sintetizan el resultado del proceso de "
        "evaluacion ambiental simplificada, indicando el estado de los "
        "impactos, medidas y programa de vigilancia.\n"
    )
    lines.append(
        "> **NOTA:** Las conclusiones tecnicas internas NO equivalen a "
        "aptitud administrativa. La calificacion del expediente la emite "
        "el organo ambiental competente mediante el Informe de Impacto Ambiental. "
        "Estas conclusiones son de uso tecnico interno.\n"
    )

    # Estado de auditoria
    lines.append("\n### I.1 Estado de auditoria interna\n")
    if audit is not None:
        audit_status = _str(_get(audit, "status"), "INCOMPLETO")
        audit_issues = _list_of(audit, "issues")
        lines.append(f"**Estado auditoria (AU-04):** `{audit_status}`\n")
        lines.append(f"**Total incidencias:** {len(audit_issues)}\n")

        if audit_status == "NO_CONFORME":
            lines.append(
                "\n> **AVISO DE AUDITORIA FINAL:** El informe final de auditoria "
                "interna califica el expediente como NO CONFORME "
                "(estado interno: `NO_CONFORME`). "
                "Las incidencias detectadas deben resolverse antes de "
                "iniciar cualquier tramite administrativo.\n"
            )
            warnings.append(
                "Auditoria final NO CONFORME. Revisar incidencias antes de tramitar."
            )
        elif audit_status in ("CONFORME_CON_OBSERVACIONES", "CON_OBSERVACIONES"):
            lines.append(
                "\n> **AVISO:** El expediente presenta observaciones internas "
                "que deben revisarse antes de su uso administrativo.\n"
            )
        elif audit_status == "INCOMPLETO":
            lines.append(
                "\n> **AVISO DE AUDITORIA FINAL:** La auditoria interna esta "
                "INCOMPLETA. Faltan controles o evidencias antes de considerar "
                "el documento como cerrable.\n"
            )
        elif audit_status == "CONFORME":
            lines.append(
                "\n> **Nota:** La calificacion CONFORME es interna y no equivale "
                "a aptitud administrativa.\n"
            )

        # Agrupar por severidad
        by_severity: dict[str, list] = {}
        for iss in audit_issues:
            sev = _str(_get(iss, "severity"), "INFO")
            by_severity.setdefault(sev, []).append(iss)

        for sev in ("BLOQUEANTE", "ALTA", "MEDIA", "BAJA", "INFO"):
            items = by_severity.get(sev, [])
            if items:
                lines.append(f"**{sev}:** {len(items)} incidencia(s)\n")
                if sev in ("BLOQUEANTE", "ALTA"):
                    for item in items[:5]:
                        lines.append(f"  - [{_get(item, 'code', '?')}] {_get(item, 'message', '?')}")
                    lines.append("")
    else:
        lines.append(
            "> _No disponible: falta `auditoria/final_audit_result.json`. "
            "Ejecute `audit-final --write`._\n"
        )

    # Efectos acumulativos y sinergicos
    lines.append("\n### I.2 Efectos acumulativos y sinergicos\n")
    if cumul is not None:
        cum_groups = _list_of(cumul, "cumulative_groups")
        syn_groups = _list_of(cumul, "synergistic_groups")
        gaps_cumul = _list_of(cumul, "unresolved_gaps") or _list_of(cumul, "gaps")
        lines.append(f"**Grupos acumulativos:** {len(cum_groups)}\n")
        lines.append(f"**Grupos sinergeticos:** {len(syn_groups)}\n")
        if gaps_cumul:
            lines.append(
                f"**Gaps no resueltos en efectos acumulativos:** {len(gaps_cumul)}\n"
            )
            warnings.append(f"{len(gaps_cumul)} gaps no resueltos en efectos acumulativos.")
    else:
        lines.append("> _Datos de efectos acumulativos no disponibles._\n")

    lines.append("\n### I.3 Sintesis\n")
    lines.append(
        "Las conclusiones de este documento son de caracter tecnico interno. "
        "No declaran aptitud administrativa. No sustituyen al Informe de Impacto "
        "Ambiental del organo ambiental competente.\n"
    )

    if missing_files:
        notice = format_missing_notice("I", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="I",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=[
            "Conclusiones tecnicas internas. No declaran aptitud administrativa.",
            "Si audit-final es NO_CONFORME, queda visible y advertido.",
        ],
    )


def build_block_j(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque J — Resumen no tecnico."""
    exp = Path(exp_path)
    title = "Resumen no tecnico"
    lines: list[str] = [_block_header("J", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    audit_path = exp / "auditoria" / "final_audit_result.json"
    pva_path = exp / "impactos" / "phase6_model_with_pva.json"
    inv_path = exp / "inventario" / "inventory_summary.json"
    conesa_path = exp / "impactos" / "phase6_model_with_conesa.json"

    audit = safe_load_json(audit_path)
    pva_data = safe_load_json(pva_path)
    inv = safe_load_json(inv_path)
    conesa_data = safe_load_json(conesa_path)

    if audit is not None:
        source_files.append("auditoria/final_audit_result.json")
    else:
        missing_files = list(set(missing_files + ["auditoria/final_audit_result.json"]))

    if pva_data is not None:
        source_files.append("impactos/phase6_model_with_pva.json")
    else:
        missing_files = list(set(missing_files + ["impactos/phase6_model_with_pva.json"]))

    lines.append(
        "Este bloque resume el contenido del Documento Ambiental en lenguaje "
        "accesible para el publico general. Su contenido refleja fielmente el "
        "contenido tecnico del documento; no lo simplifica ni suaviza.\n"
    )
    lines.append(
        "> **AVISO:** Este resumen no tecnico no modifica las valoraciones "
        "tecnicas del expediente. Los datos pendientes y gaps activos se "
        "mantienen visibles. No declara aptitud administrativa.\n"
    )

    # Descripcion basica del proyecto
    lines.append("\n### J.1 El proyecto\n")
    phase2_path = exp / "control_interno" / "phase2_result.json"
    phase2 = safe_load_json(phase2_path)
    if phase2 is not None:
        scope = _get(phase2, "scope") or {}
        promotor = _get(scope, "promotor") or _get(phase2, "promotor")
        actividad = _get(scope, "actividad") or _get(scope, "actividad_principal")
        if promotor:
            lines.append(f"El proyecto es promovido por **{_str(promotor)}**. ")
        if actividad:
            lines.append(f"La actividad principal es: **{_str(actividad)}**.\n")
        else:
            lines.append(
                "La descripcion completa del proyecto se encuentra en el Bloque A "
                "de este documento.\n"
            )
    else:
        lines.append(
            "La descripcion del proyecto se encuentra en el Bloque A "
            "de este documento. Los datos de identificacion estan pendientes "
            "de completar.\n"
        )

    # Medio ambiente afectado
    lines.append("\n### J.2 El medio ambiente evaluado\n")
    if inv is not None:
        factors = _list_of(inv, "factors")
        with_data = [
            f for f in factors
            if _get(f, "inventory_semaphore") not in ("NO_CONSTA", None)
        ]
        lines.append(
            f"Se han evaluado {len(factors)} factores ambientales. "
            f"De ellos, {len(with_data)} disponen de datos suficientes para "
            f"una caracterizacion inicial.\n"
        )
        lines.append(
            "La evaluacion se ha realizado en modo gabinete a partir de fuentes "
            "documentales y cartografia oficial. No se ha realizado prospeccion "
            "de campo.\n"
        )
    else:
        lines.append(
            "El inventario ambiental aun no esta completo. "
            "Consulte el Bloque B para el estado de cada factor.\n"
        )

    # Impactos
    lines.append("\n### J.3 Los impactos\n")
    if conesa_data is not None:
        impacts = _list_of(conesa_data, "impacts")
        negatives = [i for i in impacts if _get(i, "nature") == "NEGATIVO"]
        positives = [i for i in impacts if _get(i, "nature") == "POSITIVO"]
        indets = [
            i for i in impacts
            if _get(i, "nature") == "INDETERMINADO" or
               _get(i, "significance_without_measures") == "INDETERMINADO"
        ]
        lines.append(
            f"El proyecto genera {len(impacts)} impactos identificados: "
            f"{len(negatives)} negativos, {len(positives)} positivos "
            f"y {len(indets)} con valoracion pendiente.\n"
        )
        if indets:
            lines.append(
                f"Hay **{len(indets)} impacto(s) con valoracion aun no determinada**. "
                "Estos impactos no pueden cerrarse hasta disponer de datos adicionales. "
                "Su evaluacion definitiva corresponde al organo ambiental.\n"
            )
            warnings.append(f"{len(indets)} impactos INDETERMINADO en Bloque J.")
    else:
        lines.append(
            "La valoracion de impactos aun no esta disponible. "
            "Consulte el Bloque C para el estado de la evaluacion.\n"
        )

    # Medidas
    lines.append("\n### J.4 Las medidas\n")
    meas_path = exp / "impactos" / "phase6_model_with_measures.json"
    meas_data = safe_load_json(meas_path)
    if meas_data is not None:
        measures = _list_of(meas_data, "measures")
        real_measures = [
            m for m in measures
            if not _get(m, "is_diagnostic") and not _get(m, "is_prl_only")
        ]
        lines.append(
            f"Se proponen {len(real_measures)} medidas ambientales (preventivas, "
            f"correctoras y protectoras) para reducir los impactos identificados.\n"
        )
    else:
        lines.append(
            "Las medidas aun no estan disponibles. "
            "Consulte el Bloque D para el estado de las medidas.\n"
        )

    # PVA
    lines.append("\n### J.5 El programa de seguimiento\n")
    if pva_data is not None:
        pva_programs = _list_of(pva_data, "pva_programs")
        lines.append(
            f"Se han establecido {len(pva_programs)} fichas de vigilancia ambiental "
            "para hacer seguimiento de los impactos durante la vida util del proyecto.\n"
        )
    else:
        lines.append(
            "El programa de vigilancia ambiental aun no esta disponible. "
            "Consulte el Bloque E.\n"
        )

    # Estado general
    lines.append("\n### J.6 Estado del documento\n")
    if audit is not None:
        audit_status = _str(_get(audit, "status"), "INCOMPLETO")
        lines.append(
            f"El estado interno de la auditoria de este documento es: "
            f"**{audit_status}**. "
        )
        if audit_status == "NO_CONFORME":
            lines.append(
                "La revision interna automatica ha detectado incidencias pendientes. "
                "El documento no debe considerarse cerrado ni completado "
                "hasta resolver dichas incidencias.\n"
            )
            warnings.append(
                "Auditoria NO CONFORME en bloque J: el resumen no tecnico refleja este estado."
            )
        elif audit_status == "INCOMPLETO":
            lines.append(
                "No consta auditoria final interna completa. "
                "El documento no debe considerarse cerrado.\n"
            )
            warnings.append(
                "Auditoria INCOMPLETA en bloque J: el resumen no tecnico refleja este estado."
            )
        else:
            lines.append(
                "Este estado es de caracter tecnico interno y no implica "
                "aptitud administrativa.\n"
            )
    else:
        lines.append(
            "El estado de la auditoria interna no esta disponible. "
            "Consulte el Bloque I.\n"
        )

    if missing_files:
        notice = format_missing_notice("J", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="J",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=[
            "Resumen no tecnico fiel al contenido tecnico. No suaviza gaps.",
            "No contiene frases: sin afeccion / apto administrativamente / se descarta / todos compatibles.",
        ],
    )


def build_block_k(exp_path: "str | Path", manifest_item: Any) -> DocumentBlockBuildResult:
    """Bloque K — Anexos y documentacion complementaria."""
    exp = Path(exp_path)
    title = "Anexos y documentacion complementaria"
    lines: list[str] = [_block_header("K", title)]
    source_files: list[str] = []
    missing_files: list[str] = list(getattr(manifest_item, "missing_files", []))
    warnings: list[str] = []

    lines.append(
        "Relacion de archivos y documentos que forman parte del expediente. "
        "Solo se listan referencias; no se copian archivos.\n"
    )

    def _list_dir(dir_path: Path, section: str, description: str) -> list[str]:
        sub: list[str] = [f"\n### K.{section} {description}\n"]
        if dir_path.is_dir():
            files = sorted(dir_path.iterdir())
            if files:
                for f in files:
                    if f.is_file():
                        sub.append(f"- `{f.name}` ({f.stat().st_size} bytes)")
                    elif f.is_dir():
                        sub.append(f"- `{f.name}/` (directorio)")
                sub.append("")
                return sub
            else:
                sub.append(f"_Directorio {dir_path.name}/ vacio._\n")
                return sub
        else:
            sub.append(f"_Directorio {dir_path.name}/ no encontrado._\n")
            return sub

    # Cartografia
    cartografia_dirs = [
        exp / "cartografia",
        exp / "mapas",
    ]
    for cdir in cartografia_dirs:
        if cdir.is_dir():
            lines.extend(_list_dir(cdir, "1", f"Cartografia ({cdir.name}/)"))
            source_files.append(f"{cdir.name}/")
            break
    else:
        lines.append("\n### K.1 Cartografia\n")
        lines.append("_Directorio de cartografia no encontrado._\n")

    # Clima
    clima_dir = exp / "clima"
    if clima_dir.is_dir():
        lines.extend(_list_dir(clima_dir, "2", "Clima"))
        source_files.append("clima/")

    # Inputs
    inputs_dir = exp / "inputs"
    if inputs_dir.is_dir():
        lines.extend(_list_dir(inputs_dir, "3", "Documentos aportados por el promotor"))
        source_files.append("inputs/")
    else:
        lines.append("\n### K.3 Documentos del promotor\n")
        lines.append("_Directorio inputs/ no encontrado._\n")
        missing_files = list(set(missing_files + ["inputs"]))

    # Auditoria
    auditoria_dir = exp / "auditoria"
    if auditoria_dir.is_dir():
        lines.extend(_list_dir(auditoria_dir, "4", "Informes de auditoria interna"))
        source_files.append("auditoria/")

    # Inventario
    inventario_dir = exp / "inventario"
    if inventario_dir.is_dir():
        lines.extend(_list_dir(inventario_dir, "5", "Fichas de inventario ambiental"))
        source_files.append("inventario/")

    # Impactos
    impactos_dir = exp / "impactos"
    if impactos_dir.is_dir():
        lines.extend(_list_dir(impactos_dir, "6", "Modelos de impactos, medidas y PVA"))
        source_files.append("impactos/")

    if missing_files:
        notice = format_missing_notice("K", missing_files)
        if notice:
            lines.append(f"\n{notice}\n")

    if not source_files:
        status = "MISSING"
    elif missing_files:
        status = "PARTIAL"
    else:
        status = "GENERATED"

    return DocumentBlockBuildResult(
        block_id="K",
        title=title,
        status=status,
        source_files=source_files,
        missing_files=missing_files,
        markdown="\n".join(lines),
        warnings=warnings,
        notes=["Solo se listan referencias. No se copian archivos."],
    )


# ---------------------------------------------------------------------------
# Ensamblado del documento
# ---------------------------------------------------------------------------

def assemble_document_markdown(blocks: list[DocumentBlockBuildResult]) -> str:
    """Ensambla el markdown completo del documento a partir de los bloques."""
    lines: list[str] = []

    # Portada
    lines.append("# Documento Ambiental — Borrador tecnico")
    lines.append("")
    lines.append(f"> **{_ADMIN_DISCLAIMER}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Indice simple
    lines.append("## Indice")
    lines.append("")
    for block in blocks:
        status_icon = (
            "✓" if block.status == "GENERATED" else
            "~" if block.status == "PARTIAL" else
            "✗" if block.status == "MISSING" else
            "-"
        )
        lines.append(
            f"- [{status_icon}] **Bloque {block.block_id}** — {block.title}"
        )
    lines.append("")
    lines.append(
        "_Leyenda: ✓ GENERATED · ~ PARTIAL · ✗ MISSING · - SKIPPED_"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Advertencias globales
    missing = [b for b in blocks if b.status == "MISSING"]
    partial = [b for b in blocks if b.status == "PARTIAL"]

    if missing:
        lines.append("## Advertencias del generador")
        lines.append("")
        lines.append(
            f"> **{len(missing)} bloque(s) MISSING:** "
            f"{', '.join(b.block_id for b in missing)}. "
            f"Estos bloques no tienen inputs suficientes y no se han generado."
        )
        lines.append("")
    if partial:
        if not missing:
            lines.append("## Advertencias del generador")
            lines.append("")
        lines.append(
            f"> **{len(partial)} bloque(s) PARTIAL:** "
            f"{', '.join(b.block_id for b in partial)}. "
            f"Estos bloques tienen contenido pero faltan algunas fuentes."
        )
        lines.append("")

    if missing or partial:
        lines.append("---")
        lines.append("")

    # Bloques en orden
    block_map = {b.block_id: b for b in blocks}
    for block_id in BLOCK_ORDER:
        block = block_map.get(block_id)
        if block is None:
            continue
        if block.status == "MISSING":
            lines.append(f"## Bloque {block_id} — {block.title}")
            lines.append("")
            lines.append(
                f"> **[MISSING]** Este bloque no puede generarse porque "
                f"faltan todos los inputs requeridos. "
                f"Ejecute el pipeline tecnico completo."
            )
            if block.missing_files:
                lines.append("")
                lines.append(
                    format_missing_notice(block_id, block.missing_files)
                )
        else:
            lines.append(block.markdown)
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

_BLOCK_BUILDERS = {
    "A": build_block_a,
    "B": build_block_b,
    "C": build_block_c,
    "D": build_block_d,
    "E": build_block_e,
    "F": build_block_f,
    "G": build_block_g,
    "H": build_block_h,
    "I": build_block_i,
    "J": build_block_j,
    "K": build_block_k,
}


def build_document_markdown(
    expediente_path: "str | Path",
    write_outputs: bool = False,
) -> DocumentMarkdownBuildResult:
    """
    Genera el borrador Markdown del Documento Ambiental.

    Args:
        expediente_path: Ruta al directorio del expediente.
        write_outputs: Si True, escribe documento/ con los archivos de salida.

    Returns:
        DocumentMarkdownBuildResult con todos los bloques generados.
    """
    exp_path = Path(expediente_path)

    # Construir manifest (DOC-00)
    manifest = build_document_manifest(exp_path)

    manifest_by_id = {item.block_id: item for item in manifest.manifest_items}

    blocks: list[DocumentBlockBuildResult] = []
    generated_blocks: list[str] = []
    partial_blocks: list[str] = []
    missing_blocks: list[str] = []
    global_warnings: list[str] = list(manifest.warnings)

    for block_id in BLOCK_ORDER:
        manifest_item = manifest_by_id.get(block_id)
        builder = _BLOCK_BUILDERS.get(block_id)

        if builder is None or manifest_item is None:
            continue

        try:
            block_result = builder(exp_path, manifest_item)
        except Exception as exc:
            block_result = DocumentBlockBuildResult(
                block_id=block_id,
                title=manifest_item.title if manifest_item else f"Bloque {block_id}",
                status="MISSING",
                warnings=[f"Error interno al generar bloque {block_id}: {exc}"],
                markdown=(
                    f"## Bloque {block_id}\n\n"
                    f"> Error interno al generar este bloque: {exc}\n"
                ),
            )
            global_warnings.append(
                f"Error al generar Bloque {block_id}: {exc}"
            )

        blocks.append(block_result)

        if block_result.status == "GENERATED":
            generated_blocks.append(block_id)
        elif block_result.status == "PARTIAL":
            partial_blocks.append(block_id)
        elif block_result.status == "MISSING":
            missing_blocks.append(block_id)

    # Ensamblar markdown
    markdown_content = assemble_document_markdown(blocks)

    # Escribir si se solicita
    output_path: str | None = None
    if write_outputs:
        doc_dir = exp_path / "documento"
        doc_dir.mkdir(parents=True, exist_ok=True)

        md_out = doc_dir / DOCUMENT_OUTPUT_FILENAME
        md_out.write_text(markdown_content, encoding="utf-8")
        output_path = str(md_out)

        result_obj = DocumentMarkdownBuildResult(
            expediente_id=exp_path.name,
            output_markdown_path=output_path,
            blocks=blocks,
            generated_blocks=generated_blocks,
            partial_blocks=partial_blocks,
            missing_blocks=missing_blocks,
            warnings=global_warnings,
            notes=[
                "Este borrador no declara aptitud administrativa.",
                "Requiere revision tecnica/juridica antes de presentacion.",
            ],
        )

        json_out = doc_dir / DOCUMENT_BUILD_RESULT_FILENAME
        json_out.write_text(
            json.dumps(result_obj.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return result_obj

    return DocumentMarkdownBuildResult(
        expediente_id=exp_path.name,
        output_markdown_path=None,
        blocks=blocks,
        generated_blocks=generated_blocks,
        partial_blocks=partial_blocks,
        missing_blocks=missing_blocks,
        warnings=global_warnings,
        notes=[
            "Este borrador no declara aptitud administrativa.",
            "Requiere revision tecnica/juridica antes de presentacion.",
        ],
    )
