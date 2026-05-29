"""
document_package_builder -- DOC-06
Empaquetador final del Documento Ambiental.

Recopila los outputs documentales y de auditoria ya generados en una carpeta
estructurada documento/paquete_entrega/ lista para revision tecnica.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica DOCX, Markdown ni fuentes.
  - No genera PDF.
  - No genera ZIP.
  - No declara aptitud administrativa.
  - Solo copia; no escribe salvo write_outputs=True.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

PACKAGE_DIR_NAME = "paquete_entrega"
PACKAGE_RESULT_JSON = "package_build_result.json"
PACKAGE_RESULT_MD = "package_build_result.md"

PACKAGE_SECTIONS: list[str] = [
    "01_documento_ambiental",
    "02_auditorias",
    "03_anexos_graficos",
    "04_trazabilidad",
]

# Archivos del documento principal (rutas relativas al expediente)
PRIORITY_DOCUMENT_FILES: list[str] = [
    "documento/documento_ambiental_borrador_con_figuras.docx",
    "documento/documento_ambiental_borrador.docx",
    "documento/documento_ambiental_borrador.md",
]

# Archivos de auditoria (rutas relativas al expediente)
AUDIT_FILES: list[str] = [
    "auditoria/final_audit_result.json",
    "auditoria/final_audit_result.md",
    "documento/document_quality_result.json",
    "documento/document_quality_result.md",
    "auditoria/art45_checklist_result.json",
    "auditoria/prudence_validation_result.json",
    "auditoria/traceability_validation_result.json",
    "auditoria/block_consistency_result.json",
    "auditoria/conesa_check_result.json",
    "auditoria/diagnostic_measure_validation_result.json",
    "auditoria/prl_measure_validation_result.json",
    "auditoria/conditional_chain_result.json",
    "auditoria/conditional_chain_result.md",
]

# Archivos de trazabilidad
TRACEABILITY_FILES: list[str] = [
    "documento/document_manifest.json",
    "documento/document_manifest.md",
    "documento/document_build_result.json",
    "documento/docx_build_result.json",
    "documento/document_figures_result.json",
    "documento/document_figures_result.md",
]

# Archivos de figuras/anexos (para la seccion 03_anexos_graficos)
FIGURE_RESULT_FILES: list[str] = [
    "documento/document_figures_result.md",
]

# Archivos requeridos: su ausencia bloquea is_success
_REQUIRED_FILES: set[str] = {
    "documento/documento_ambiental_borrador.docx",
    "documento/documento_ambiental_borrador.md",
}

# Destinos dentro del paquete por archivo fuente
# FIGURE_RESULT_FILES se procesa al final para que sus entradas tengan prioridad
# sobre TRACEABILITY_FILES (document_figures_result.md va a 03, no a 04)
_FILE_TO_SECTION: dict[str, str] = {}
for _f in PRIORITY_DOCUMENT_FILES:
    _FILE_TO_SECTION[_f] = "01_documento_ambiental"
for _f in AUDIT_FILES:
    _FILE_TO_SECTION[_f] = "02_auditorias"
for _f in TRACEABILITY_FILES:
    _FILE_TO_SECTION[_f] = "04_trazabilidad"
for _f in FIGURE_RESULT_FILES:
    _FILE_TO_SECTION[_f] = "03_anexos_graficos"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PackageFile:
    """Representa un archivo a incluir en el paquete de entrega."""

    source_path: str
    package_path: str
    exists: bool
    copied: bool
    file_size_bytes: int
    required: bool
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "package_path": self.package_path,
            "exists": self.exists,
            "copied": self.copied,
            "file_size_bytes": self.file_size_bytes,
            "required": self.required,
            "warnings": self.warnings,
            "notes": self.notes,
        }

    def summary(self) -> str:
        status = "OK" if self.copied else ("FALTA" if self.exists else "NO_EXISTE")
        req = "REQUERIDO" if self.required else "OPCIONAL"
        return f"[{status}][{req}] {self.source_path} -> {self.package_path}"


@dataclass
class DocumentPackageResult:
    """Resultado completo del empaquetado documental."""

    expediente_id: str
    package_dir: "str | None"
    generated: bool
    files: list[PackageFile] = field(default_factory=list)
    required_missing: list[str] = field(default_factory=list)
    optional_missing: list[str] = field(default_factory=list)
    copied_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def copied_count(self) -> int:
        return len(self.copied_files)

    def missing_required_count(self) -> int:
        return len(self.required_missing)

    def missing_optional_count(self) -> int:
        return len(self.optional_missing)

    def is_success(self) -> bool:
        return self.generated and len(self.required_missing) == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "package_dir": self.package_dir,
            "generated": self.generated,
            "files": [f.to_dict() for f in self.files],
            "required_missing": self.required_missing,
            "optional_missing": self.optional_missing,
            "copied_files": self.copied_files,
            "warnings": self.warnings,
            "notes": self.notes,
            "copied_count": self.copied_count(),
            "missing_required_count": self.missing_required_count(),
            "missing_optional_count": self.missing_optional_count(),
            "is_success": self.is_success(),
        }

    def summary(self) -> str:
        status = "GENERADO" if self.generated else "NO_GENERADO (dry-run)"
        lines = [
            f"Empaquetado: {status}",
            f"  Expediente : {self.expediente_id}",
            f"  Archivos copiados : {self.copied_count()}",
            f"  Requeridos faltantes: {self.missing_required_count()}",
            f"  Opcionales faltantes: {self.missing_optional_count()}",
        ]
        if self.package_dir:
            lines.append(f"  Directorio : {self.package_dir}")
        if self.required_missing:
            lines.append("  REQUERIDOS FALTANTES:")
            for f in self.required_missing:
                lines.append(f"    - {f}")
        if self.warnings:
            for w in self.warnings[:5]:
                lines.append(f"  [AVISO] {w}")
        result_str = "OK" if self.is_success() else (
            "PARCIAL (requeridos faltantes)" if self.generated else "SIN ARCHIVOS ESCRITOS"
        )
        lines.append(f"  RESULTADO: {result_str}")
        lines.append(
            "  AVISO: Este paquete no declara aptitud para presentacion administrativa."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones de soporte
# ---------------------------------------------------------------------------

def safe_copy_file(source: "str | Path", destination: "str | Path") -> bool:
    """Copia un archivo preservando contenido. Crea carpetas padre. Devuelve True/False."""
    src = Path(source)
    dst = Path(destination)
    if not src.exists():
        return False
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return True
    except Exception:
        return False


def _package_destination(rel_source: str, package_dir: Path) -> str:
    """Devuelve la ruta destino dentro del paquete para un archivo fuente."""
    section = _FILE_TO_SECTION.get(rel_source, "04_trazabilidad")
    filename = Path(rel_source).name
    return str(package_dir / section / filename)


def collect_package_files(
    expediente_path: "str | Path",
) -> list[PackageFile]:
    """
    Prepara la lista de archivos a empaquetar sin copiar nada.
    Asigna destinos dentro de paquete_entrega.
    """
    exp = Path(expediente_path)
    package_dir = exp / "documento" / PACKAGE_DIR_NAME
    result: list[PackageFile] = []
    seen_sources: set[str] = set()

    all_files: list[tuple[str, bool]] = []
    for rel in PRIORITY_DOCUMENT_FILES:
        all_files.append((rel, rel in _REQUIRED_FILES))
    for rel in AUDIT_FILES:
        if rel not in seen_sources:
            all_files.append((rel, False))
    # document_figures_result.md va a 03_anexos_graficos (ya en FIGURE_RESULT_FILES)
    for rel in FIGURE_RESULT_FILES:
        if rel not in [r for r, _ in all_files]:
            all_files.append((rel, False))
    for rel in TRACEABILITY_FILES:
        if rel not in [r for r, _ in all_files]:
            all_files.append((rel, False))

    # Verificar DOCX enriquecido: si figures_result.json tiene generated=True
    # y el DOCX no existe, emitir warning
    figs_json_path = exp / "documento" / "document_figures_result.json"
    enriched_required = False
    if figs_json_path.exists():
        try:
            with open(figs_json_path, encoding="utf-8") as fh:
                figs_data = json.load(fh)
            if figs_data.get("generated") is True:
                enriched_required = True
        except Exception:
            pass

    for rel, required in all_files:
        if rel in seen_sources:
            continue
        seen_sources.add(rel)

        src = exp / rel
        exists = src.exists()
        size = src.stat().st_size if exists else 0
        dest = _package_destination(rel, package_dir)

        warnings: list[str] = []
        if rel == "documento/documento_ambiental_borrador_con_figuras.docx":
            if enriched_required and not exists:
                warnings.append(
                    "document_figures_result.json indica generated=True "
                    "pero el DOCX enriquecido no existe."
                )

        result.append(PackageFile(
            source_path=str(src),
            package_path=dest,
            exists=exists,
            copied=False,
            file_size_bytes=size,
            required=required or (rel in _REQUIRED_FILES),
            warnings=warnings,
        ))

    return result


# ---------------------------------------------------------------------------
# Generadores de texto
# ---------------------------------------------------------------------------

def build_readme_entrega(result: DocumentPackageResult) -> str:
    """Genera README_ENTREGA.md para el paquete de entrega."""
    lines: list[str] = [
        "# Paquete de entrega — Documento Ambiental",
        "",
        f"**Expediente:** {result.expediente_id}",
        f"**Estado del paquete:** {'GENERADO' if result.generated else 'PRELIMINAR (dry-run)'}",
        f"**Archivos incluidos:** {result.copied_count()}",
        "",
        "---",
        "",
        "## 1. Contenido del paquete",
        "",
        "| Carpeta | Contenido |",
        "|---------|-----------|",
        "| `01_documento_ambiental/` | Borradores DOCX y Markdown del Documento Ambiental |",
        "| `02_auditorias/` | Resultados de auditorias internas (art.45, prudencia, trazabilidad, QC) |",
        "| `03_anexos_graficos/` | Resultados de insercion de figuras y anexos graficos |",
        "| `04_trazabilidad/` | Manifest, build results y trazabilidad del proceso documental |",
        "",
        "## 2. Documento principal",
        "",
    ]

    doc_files = [f for f in result.files if "01_documento_ambiental" in f.package_path]
    if doc_files:
        for pf in doc_files:
            estado = "Incluido" if pf.copied else "No disponible"
            lines.append(f"- `{Path(pf.package_path).name}`: {estado}")
    else:
        lines.append("_Sin archivos de documento principal disponibles._")

    lines += [
        "",
        "## 3. Auditorias internas",
        "",
    ]
    audit_files = [f for f in result.files if "02_auditorias" in f.package_path]
    if audit_files:
        for pf in audit_files:
            estado = "Incluido" if pf.copied else "No disponible"
            lines.append(f"- `{Path(pf.package_path).name}`: {estado}")
    else:
        lines.append("_Sin auditorias disponibles._")

    lines += [
        "",
        "## 4. Anexos graficos y trazabilidad",
        "",
    ]
    other_files = [
        f for f in result.files
        if "03_anexos_graficos" in f.package_path or "04_trazabilidad" in f.package_path
    ]
    if other_files:
        for pf in other_files:
            estado = "Incluido" if pf.copied else "No disponible"
            lines.append(f"- `{Path(pf.source_path).name}`: {estado}")
    else:
        lines.append("_Sin archivos de trazabilidad disponibles._")

    lines += [
        "",
        "## 5. Archivos faltantes",
        "",
    ]
    if result.required_missing:
        lines.append("### Requeridos")
        lines.append("")
        for f in result.required_missing:
            lines.append(f"- `{f}` — **REQUERIDO** — debe generarse antes de presentacion")
    if result.optional_missing:
        lines.append("")
        lines.append("### Opcionales")
        lines.append("")
        for f in result.optional_missing:
            lines.append(f"- `{f}` — opcional")
    if not result.required_missing and not result.optional_missing:
        lines.append("_Todos los archivos esperados estan presentes._")

    lines += [
        "",
        "## 6. Advertencia de alcance",
        "",
        "> **Este paquete no declara el expediente apto para presentacion administrativa.**",
        "> Debe ser revisado por tecnico competente antes de su uso.",
        "> El presente paquete es un borrador de trabajo para revision tecnica interna.",
        "> La presentacion administrativa requiere firma y validacion tecnica/juridica completa.",
        "",
    ]

    if result.warnings:
        lines += ["## 7. Advertencias del empaquetado", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def build_package_report_markdown(result: DocumentPackageResult) -> str:
    """Genera el informe de empaquetado en formato Markdown."""
    status = "GENERADO" if result.generated else "DRY-RUN (sin archivos escritos)"
    lines: list[str] = [
        "# Resultado de empaquetado documental",
        "",
        f"**Expediente:** {result.expediente_id}",
        f"**Estado:** {status}",
        f"**Archivos copiados:** {result.copied_count()}",
        f"**Requeridos faltantes:** {result.missing_required_count()}",
        f"**Opcionales faltantes:** {result.missing_optional_count()}",
        "",
        "---",
        "",
        "## 1. Resumen",
        "",
    ]

    if result.is_success():
        lines.append(
            "El paquete de entrega se ha generado correctamente. "
            "Todos los archivos requeridos estan presentes."
        )
    elif result.generated and result.required_missing:
        lines.append(
            "El paquete se ha generado pero faltan archivos requeridos. "
            "Revisar la lista de faltantes antes de la revision tecnica."
        )
    else:
        lines.append(
            "Modo dry-run: no se han copiado archivos. "
            "Use --write para generar el paquete."
        )

    lines += [
        "",
        "## 2. Archivos copiados",
        "",
    ]
    if result.copied_files:
        for f in result.copied_files:
            lines.append(f"- {f}")
    else:
        lines.append("_Sin archivos copiados._")

    lines += [
        "",
        "## 3. Archivos requeridos faltantes",
        "",
    ]
    if result.required_missing:
        for f in result.required_missing:
            lines.append(f"- **{f}** — REQUERIDO")
    else:
        lines.append("_Sin requeridos faltantes._")

    lines += [
        "",
        "## 4. Archivos opcionales faltantes",
        "",
    ]
    if result.optional_missing:
        for f in result.optional_missing:
            lines.append(f"- {f}")
    else:
        lines.append("_Sin opcionales faltantes._")

    lines += [
        "",
        "## 5. Advertencias",
        "",
    ]
    if result.warnings:
        for w in result.warnings:
            lines.append(f"- {w}")
    else:
        lines.append("_Sin advertencias._")

    lines += [
        "",
        "## 6. Advertencia de alcance",
        "",
        "> Este paquete no declara el expediente apto para presentacion administrativa.",
        "> El resultado de este empaquetado es orientativo para la revision tecnica interna.",
        "> La presentacion administrativa requiere revision tecnica/juridica completa.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

def build_document_package(
    expediente_path: "str | Path",
    write_outputs: bool = False,
    overwrite: bool = True,
) -> DocumentPackageResult:
    """
    Construye el paquete de entrega del Documento Ambiental.

    Si write_outputs=False (default): solo analiza, no copia nada.
    Si write_outputs=True: crea documento/paquete_entrega/, copia archivos,
    genera README_ENTREGA.md, package_build_result.json y .md.

    overwrite=True (default): sobreescribe paquete_entrega/ existente.
    """
    exp = Path(expediente_path)
    expediente_id = exp.name
    package_dir = exp / "documento" / PACKAGE_DIR_NAME

    package_files = collect_package_files(exp)

    required_missing: list[str] = []
    optional_missing: list[str] = []
    all_warnings: list[str] = []

    for pf in package_files:
        if pf.warnings:
            all_warnings.extend(pf.warnings)
        if not pf.exists:
            if pf.required:
                required_missing.append(pf.source_path)
            else:
                optional_missing.append(pf.source_path)

    if not write_outputs:
        return DocumentPackageResult(
            expediente_id=expediente_id,
            package_dir=None,
            generated=False,
            files=package_files,
            required_missing=required_missing,
            optional_missing=optional_missing,
            copied_files=[],
            warnings=all_warnings,
            notes=[
                "Modo dry-run: no se han copiado archivos.",
                "Use write_outputs=True para generar el paquete.",
            ],
        )

    # Crear estructura de paquete
    if overwrite and package_dir.exists():
        shutil.rmtree(str(package_dir))
    for section in PACKAGE_SECTIONS:
        (package_dir / section).mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []

    for pf in package_files:
        if not pf.exists:
            continue
        ok = safe_copy_file(pf.source_path, pf.package_path)
        if ok:
            pf.copied = True
            pf.file_size_bytes = Path(pf.source_path).stat().st_size
            copied_files.append(pf.package_path)
        else:
            all_warnings.append(f"No se pudo copiar: {pf.source_path}")

    # Generar README_ENTREGA.md
    partial_result = DocumentPackageResult(
        expediente_id=expediente_id,
        package_dir=str(package_dir),
        generated=True,
        files=package_files,
        required_missing=required_missing,
        optional_missing=optional_missing,
        copied_files=copied_files,
        warnings=all_warnings,
        notes=[
            "Este paquete no declara aptitud para presentacion administrativa.",
            "Revisar con tecnico competente antes de cualquier uso.",
        ],
    )

    readme_content = build_readme_entrega(partial_result)
    readme_path = package_dir / "README_ENTREGA.md"
    readme_path.write_text(readme_content, encoding="utf-8")

    return partial_result


def write_package_build_outputs(
    result: DocumentPackageResult,
    output_dir: "str | Path",
) -> "tuple[Path, Path]":
    """
    Escribe package_build_result.json y package_build_result.md.
    Devuelve (path_json, path_md).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / PACKAGE_RESULT_JSON
    md_path = out / PACKAGE_RESULT_MD

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

    md_content = build_package_report_markdown(result)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
