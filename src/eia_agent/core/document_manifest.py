"""
document_manifest -- DOC-00
Manifest determinista del Documento Ambiental.

Define la estructura maestra del Documento Ambiental (bloques A-K) y relaciona
cada bloque con los outputs ya generados por el pipeline tecnico.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No redacta el documento final.
  - No genera DOCX.
  - No corrige outputs del pipeline.
  - No declara aptitud administrativa.
  - Solo comprueba existencia de archivos; no los carga.
  - No modifica el expediente salvo escritura del manifest (--write).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

DOCUMENT_BLOCKS: list[tuple[str, str]] = [
    ("A", "Identificacion y descripcion del proyecto"),
    ("B", "Inventario ambiental"),
    ("C", "Identificacion y valoracion de impactos"),
    ("D", "Medidas preventivas, correctoras, protectoras, diagnosticas y documentales"),
    ("E", "Programa de vigilancia ambiental"),
    ("F", "Vulnerabilidad ante riesgos y catastrofes"),
    ("G", "Alternativas y justificacion de solucion adoptada"),
    ("H", "Red Natura 2000 y espacios naturales protegidos"),
    ("I", "Conclusiones tecnicas"),
    ("J", "Resumen no tecnico"),
    ("K", "Anexos y documentacion complementaria"),
]

MANIFEST_STATUS: list[str] = ["READY", "PARTIAL", "MISSING"]

# Archivos requeridos por bloque (rutas relativas al directorio del expediente).
# Las entradas que son directorios se comprueban como Path.is_dir().
# Las entradas que son archivos se comprueban como Path.is_file().
DOCUMENT_REQUIRED_INPUTS: dict[str, list[str]] = {
    "A": [
        "impactos/phase6_actions.json",
        "capas/hechos_confirmados.json",
    ],
    "B": [
        "inventario/inventory_summary.json",
        "inventario/phase5_gate_result.json",
    ],
    "C": [
        "impactos/phase6_model_with_conesa.json",
        "impactos/phase6_model_with_impacts.json",
        "impactos/cumulative_synergistic_result.json",
        "auditoria/conesa_check_result.json",
    ],
    "D": [
        "impactos/phase6_model_with_measures.json",
        "auditoria/diagnostic_measure_validation_result.json",
        "auditoria/prl_measure_validation_result.json",
    ],
    "E": [
        "impactos/phase6_model_with_pva.json",
        "impactos/pva_coverage_result.json",
    ],
    "F": [
        "inventario/inventory_summary.json",
        "impactos/phase6_model_with_conesa.json",
    ],
    "G": [
        "capas/normativa_aplicable.json",
        "capas/hechos_confirmados.json",
    ],
    "H": [
        "inventario/inventory_summary.json",
        "impactos/phase6_model_with_conesa.json",
        "auditoria/block_consistency_result.json",
    ],
    "I": [
        "auditoria/final_audit_result.json",
        "impactos/cumulative_synergistic_result.json",
    ],
    "J": [
        "auditoria/final_audit_result.json",
        "impactos/phase6_model_with_pva.json",
    ],
    "K": [
        "inputs",
        "capas",
        "clima",
    ],
}

DOCUMENT_OPTIONAL_INPUTS: dict[str, list[str]] = {
    "A": [
        "control_interno/phase2_result.json",
        "impactos/impact_identification_result.json",
    ],
    "B": [
        "inventario/resumen_inventario.md",
        "fichas_inventario",
    ],
    "C": [
        "impactos/C5_acumulativos_sinergicos.md",
        "impactos/conesa_assignment_result.json",
    ],
    "D": [
        "impactos/measure_generation_result.json",
    ],
    "E": [
        "impactos/pva_generation_result.json",
        "impactos/pva_coverage_result.md",
    ],
    "F": [
        "capas/cartografia_trace.json",
        "capas/inferencias_y_gaps.json",
    ],
    "G": [
        "control_interno/phase3_result.json",
        "capas/inferencias_y_gaps.json",
    ],
    "H": [
        "capas/inferencias_y_gaps.json",
        "auditoria/traceability_validation_result.json",
    ],
    "I": [
        "auditoria/final_audit_result.md",
        "auditoria/prudence_validation_result.json",
    ],
    "J": [],
    "K": [
        "mapas",
        "anejos",
        "cartografia",
    ],
}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _path_exists(exp_path: Path, rel: str) -> bool:
    """True si la ruta relativa existe (file o directory)."""
    return (exp_path / rel).exists()


def _determine_status(
    required: list[str], existing: list[str]
) -> str:
    """READY / PARTIAL / MISSING segun cuantos required estan en existing."""
    if not required:
        return "MISSING"
    n = len(existing)
    total = len(required)
    if n == total:
        return "READY"
    if n > 0:
        return "PARTIAL"
    return "MISSING"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DocumentManifestItem:
    """Estado del manifest para un bloque del Documento Ambiental."""

    block_id: str
    title: str
    required_files: list[str] = field(default_factory=list)
    optional_files: list[str] = field(default_factory=list)
    existing_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    status: str = "MISSING"
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "title": self.title,
            "status": self.status,
            "required_files": list(self.required_files),
            "optional_files": list(self.optional_files),
            "existing_files": list(self.existing_files),
            "missing_files": list(self.missing_files),
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        n = len(self.existing_files)
        total = len(self.required_files)
        return (
            f"[{self.status:7}] Bloque {self.block_id} — {self.title[:50]} "
            f"({n}/{total} inputs)"
        )


@dataclass
class DocumentManifestResult:
    """Resultado completo del manifest del Documento Ambiental."""

    expediente_id: str
    manifest_items: list[DocumentManifestItem] = field(default_factory=list)
    ready_blocks: list[str] = field(default_factory=list)
    partial_blocks: list[str] = field(default_factory=list)
    missing_blocks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    # administrative_ready siempre False
    administrative_ready: bool = False

    def ready_count(self) -> int:
        return len(self.ready_blocks)

    def partial_count(self) -> int:
        return len(self.partial_blocks)

    def missing_count(self) -> int:
        return len(self.missing_blocks)

    def is_ready_for_markdown_generation(self) -> bool:
        """True si no hay bloques MISSING (puede haber PARTIAL con advertencias)."""
        return len(self.missing_blocks) == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "administrative_ready": self.administrative_ready,
            "ready_blocks": list(self.ready_blocks),
            "partial_blocks": list(self.partial_blocks),
            "missing_blocks": list(self.missing_blocks),
            "ready_count": self.ready_count(),
            "partial_count": self.partial_count(),
            "missing_count": self.missing_count(),
            "is_ready_for_markdown_generation": self.is_ready_for_markdown_generation(),
            "manifest_items": [i.to_dict() for i in self.manifest_items],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        total = len(self.manifest_items)
        return (
            f"DOC-00 [{self.expediente_id}] "
            f"{self.ready_count()} READY / "
            f"{self.partial_count()} PARTIAL / "
            f"{self.missing_count()} MISSING "
            f"de {total} bloques"
        )


# ---------------------------------------------------------------------------
# build_document_manifest
# ---------------------------------------------------------------------------


def build_document_manifest(
    expediente_path: "str | Path",
) -> DocumentManifestResult:
    """Construye el manifest del Documento Ambiental para un expediente.

    Comprueba la existencia de cada archivo requerido por bloque.
    No carga JSON. No falla por archivos ausentes.
    Si el directorio del expediente no existe, lanza FileNotFoundError.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(
            f"Directorio de expediente no encontrado: {exp_path}"
        )

    items: list[DocumentManifestItem] = []
    ready_blocks: list[str] = []
    partial_blocks: list[str] = []
    missing_blocks: list[str] = []
    global_warnings: list[str] = []

    for block_id, title in DOCUMENT_BLOCKS:
        required = DOCUMENT_REQUIRED_INPUTS.get(block_id, [])
        optional = DOCUMENT_OPTIONAL_INPUTS.get(block_id, [])

        existing_req: list[str] = []
        missing_req: list[str] = []
        for rel in required:
            if _path_exists(exp_path, rel):
                existing_req.append(rel)
            else:
                missing_req.append(rel)

        existing_opt: list[str] = [
            rel for rel in optional if _path_exists(exp_path, rel)
        ]

        status = _determine_status(required, existing_req)

        block_notes: list[str] = []
        block_warnings: list[str] = []

        if status == "PARTIAL":
            block_warnings.append(
                f"Faltan {len(missing_req)} de {len(required)} inputs requeridos. "
                f"Bloque incompleto para redaccion."
            )
        elif status == "MISSING":
            block_warnings.append(
                "No hay inputs requeridos disponibles. "
                "Este bloque no puede redactarse todavia."
            )

        item = DocumentManifestItem(
            block_id=block_id,
            title=title,
            required_files=required,
            optional_files=optional,
            existing_files=existing_req + existing_opt,
            missing_files=missing_req,
            status=status,
            notes=block_notes,
            warnings=block_warnings,
        )
        items.append(item)

        if status == "READY":
            ready_blocks.append(block_id)
        elif status == "PARTIAL":
            partial_blocks.append(block_id)
        else:
            missing_blocks.append(block_id)

    if missing_blocks:
        global_warnings.append(
            f"Bloques sin inputs suficientes: {', '.join(missing_blocks)}. "
            f"No se puede generar el Documento Ambiental completo todavia."
        )

    return DocumentManifestResult(
        expediente_id=exp_path.name,
        manifest_items=items,
        ready_blocks=ready_blocks,
        partial_blocks=partial_blocks,
        missing_blocks=missing_blocks,
        warnings=global_warnings,
        notes=[
            "Este manifest no genera el documento final.",
            "La calificacion del expediente la determina el organo ambiental competente.",
        ],
    )


# ---------------------------------------------------------------------------
# build_document_manifest_markdown
# ---------------------------------------------------------------------------


def build_document_manifest_markdown(result: DocumentManifestResult) -> str:
    """Genera el informe del manifest en markdown."""
    lines: list[str] = []

    lines.append("# Manifest del Documento Ambiental")
    lines.append("")

    # ── 1. Resumen ──
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append(f"**Expediente:** {result.expediente_id}")
    lines.append(f"**Bloques READY:** {result.ready_count()}")
    lines.append(f"**Bloques PARTIAL:** {result.partial_count()}")
    lines.append(f"**Bloques MISSING:** {result.missing_count()}")
    lines.append(
        f"**Listo para generacion markdown:** "
        f"{'Si' if result.is_ready_for_markdown_generation() else 'No'}"
    )
    lines.append(f"**Aptitud administrativa:** NO DECLARADA (`administrative_ready = False`)")
    lines.append("")

    # ── 2. Estado por bloque ──
    lines.append("## 2. Estado por bloque")
    lines.append("")
    lines.append("| Bloque | Titulo | Estado | Inputs OK | Inputs faltantes |")
    lines.append("|--------|--------|--------|-----------|-----------------|")
    for item in result.manifest_items:
        n_ok = len(item.existing_files)
        n_miss = len(item.missing_files)
        total = len(item.required_files)
        title_short = item.title[:40] + ("..." if len(item.title) > 40 else "")
        lines.append(
            f"| {item.block_id} | {title_short} | {item.status} "
            f"| {n_ok}/{total} | {n_miss} |"
        )
    lines.append("")

    # ── 3. Archivos existentes ──
    lines.append("## 3. Archivos existentes por bloque")
    lines.append("")
    for item in result.manifest_items:
        if item.existing_files:
            lines.append(f"### Bloque {item.block_id}")
            for f in item.existing_files:
                lines.append(f"- `{f}`")
            lines.append("")

    # ── 4. Archivos faltantes ──
    lines.append("## 4. Archivos faltantes")
    lines.append("")
    all_missing = [
        (item.block_id, f)
        for item in result.manifest_items
        for f in item.missing_files
    ]
    if all_missing:
        for block_id, f in all_missing:
            lines.append(f"- **[Bloque {block_id}]** `{f}`")
    else:
        lines.append("_Ningun archivo requerido falta._")
    lines.append("")

    # ── 5. Advertencias ──
    lines.append("## 5. Advertencias")
    lines.append("")
    all_warnings = list(result.warnings)
    for item in result.manifest_items:
        for w in item.warnings:
            all_warnings.append(f"[Bloque {item.block_id}] {w}")
    if all_warnings:
        for w in all_warnings:
            lines.append(f"- {w}")
    else:
        lines.append("_Sin advertencias._")
    lines.append("")

    # ── 6. Siguiente paso recomendado ──
    lines.append("## 6. Siguiente paso recomendado")
    lines.append("")
    if result.is_ready_for_markdown_generation():
        lines.append(
            "Todos los bloques tienen inputs suficientes. "
            "Se puede iniciar la generacion del Documento Ambiental (DOC-01)."
        )
    elif result.missing_count() > 0:
        missing_str = ", ".join(f"Bloque {b}" for b in result.missing_blocks)
        lines.append(
            f"Los siguientes bloques carecen de inputs: {missing_str}. "
            f"Ejecute el pipeline tecnico completo (`run-technical-pipeline --write`) "
            f"para generar los archivos necesarios."
        )
    lines.append("")
    lines.append(
        "> **Este manifest no genera el documento final y no declara aptitud "
        "administrativa. La aptitud del expediente la determina el organo ambiental "
        "competente.**"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# write_document_manifest_outputs
# ---------------------------------------------------------------------------


def write_document_manifest_outputs(
    result: DocumentManifestResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe document_manifest.json y document_manifest.md en output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "document_manifest.json"
    md_path = out / "document_manifest.md"

    json_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(
        build_document_manifest_markdown(result),
        encoding="utf-8",
    )

    return json_path, md_path
