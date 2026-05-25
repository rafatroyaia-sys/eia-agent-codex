"""
document_exporter -- DOC-07
Exportacion ZIP y PDF del paquete documental final.

Genera:
  - documento/paquete_entrega.zip  (obligatorio si paquete_entrega/ existe)
  - documento/documento_ambiental_borrador_con_figuras.pdf  (best-effort)

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica DOCX, Markdown ni fuentes.
  - No modifica paquete_entrega/.
  - No declara aptitud administrativa.
  - Solo escribe ZIP/PDF/JSONs si write_outputs=True.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

EXPORT_RESULT_JSON = "document_export_result.json"
EXPORT_RESULT_MD = "document_export_result.md"

PACKAGE_ZIP_FILENAME = "paquete_entrega.zip"
PDF_OUTPUT_FILENAME = "documento_ambiental_borrador_con_figuras.pdf"

DEFAULT_PACKAGE_DIR = "documento/paquete_entrega"
DEFAULT_DOCX_SOURCE = "documento/documento_ambiental_borrador_con_figuras.docx"


class EXPORT_STATUS:
    OK = "OK"
    CON_OBSERVACIONES = "CON_OBSERVACIONES"
    NO_CONFORME = "NO_CONFORME"
    SIN_DATOS = "SIN_DATOS"


class EXPORT_SEVERITY:
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class PDF_EXPORT_STATUS:
    GENERATED = "GENERATED"
    SKIPPED_NO_CONVERTER = "SKIPPED_NO_CONVERTER"
    FAILED = "FAILED"
    NOT_REQUESTED = "NOT_REQUESTED"
    SOURCE_MISSING = "SOURCE_MISSING"


# Nombres de componentes de ruta excluidos del ZIP
_ZIP_EXCLUDE_NAMES: frozenset[str] = frozenset({
    "__pycache__",
    ".pytest_cache",
    "thumbs.db",
    "desktop.ini",
})

# Prefijo de archivos temporales de Office
_ZIP_EXCLUDE_PREFIX = "~$"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ExportIssue:
    """Incidencia registrada durante el proceso de exportacion."""

    severity: str
    code: str
    message: str
    recommendation: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }

    def summary(self) -> str:
        return f"[{self.severity}][{self.code}] {self.message}"


@dataclass
class DocumentExportResult:
    """Resultado completo de la exportacion documental."""

    expediente_id: str
    package_dir: "str | None"
    zip_path: "str | None"
    pdf_source_docx: "str | None"
    pdf_path: "str | None"
    zip_generated: bool
    pdf_status: str
    files_zipped: list[str] = field(default_factory=list)
    issues: list[ExportIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def issue_count(self) -> int:
        return len(self.issues)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == EXPORT_SEVERITY.ERROR)

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == EXPORT_SEVERITY.WARNING)

    def files_zipped_count(self) -> int:
        return len(self.files_zipped)

    def is_success(self) -> bool:
        """True si el ZIP se genero correctamente y no hay errores. El PDF no bloquea."""
        return self.zip_generated and self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "package_dir": self.package_dir,
            "zip_path": self.zip_path,
            "pdf_source_docx": self.pdf_source_docx,
            "pdf_path": self.pdf_path,
            "zip_generated": self.zip_generated,
            "pdf_status": self.pdf_status,
            "files_zipped": self.files_zipped,
            "files_zipped_count": self.files_zipped_count(),
            "issues": [i.to_dict() for i in self.issues],
            "warnings": self.warnings,
            "notes": self.notes,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "is_success": self.is_success(),
        }

    def summary(self) -> str:
        zip_label = "GENERADO" if self.zip_generated else "NO_GENERADO"
        lines = [
            f"Exportacion: {zip_label}",
            f"  Expediente    : {self.expediente_id}",
            f"  ZIP           : {zip_label} ({self.files_zipped_count()} archivos)",
            f"  PDF           : {self.pdf_status}",
            f"  Errores       : {self.error_count()}",
            f"  Advertencias  : {self.warning_count()}",
        ]
        if self.zip_path:
            lines.append(f"  ZIP ruta      : {self.zip_path}")
        if self.pdf_path:
            lines.append(f"  PDF ruta      : {self.pdf_path}")
        if self.issues:
            for issue in self.issues[:5]:
                lines.append(f"  {issue.summary()}")
        if self.warnings:
            for w in self.warnings[:3]:
                lines.append(f"  [AVISO] {w}")
        if self.zip_generated and self.error_count() == 0:
            result_str = "OK"
        elif self.zip_generated:
            result_str = "PARCIAL (ZIP generado con errores)"
        else:
            result_str = "FALLO (ZIP no generado)"
        lines.append(f"  RESULTADO     : {result_str}")
        lines.append(
            "  AVISO: Esta exportacion no declara el expediente"
            " apto para presentacion administrativa."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deteccion de conversores
# ---------------------------------------------------------------------------

def find_soffice_executable() -> "str | None":
    """Localiza el ejecutable de LibreOffice/soffice. Devuelve ruta o None."""
    for name in ("soffice", "soffice.exe", "libreoffice", "libreoffice.exe"):
        found = shutil.which(name)
        if found:
            return found
    typical_windows = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for p in typical_windows:
        if os.path.exists(p):
            return p
    return None


def can_use_word_com() -> bool:
    """True solo si plataforma Windows y pywin32 disponible."""
    if platform.system() != "Windows":
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


# ---------------------------------------------------------------------------
# Creacion de ZIP
# ---------------------------------------------------------------------------

def _should_exclude(rel_parts: tuple[str, ...]) -> bool:
    """Devuelve True si alguna parte de la ruta relativa debe excluirse del ZIP."""
    for part in rel_parts:
        part_lower = part.lower()
        if part_lower in _ZIP_EXCLUDE_NAMES:
            return True
        if part_lower.startswith(_ZIP_EXCLUDE_PREFIX):
            return True
    return False


def create_zip_from_directory(
    source_dir: "str | Path",
    output_zip_path: "str | Path",
    exclude_patterns: "list[str] | None" = None,
) -> list[str]:
    """
    Crea un ZIP del directorio source_dir con rutas relativas limpias.

    Excluye por defecto: __pycache__, .pytest_cache, thumbs.db, desktop.ini, ~$*.
    Parametro exclude_patterns: nombres adicionales a excluir (componentes de ruta exactos).
    Devuelve lista de rutas relativas incluidas en el ZIP.
    Lanza FileNotFoundError si source_dir no existe.
    """
    src = Path(source_dir)
    if not src.exists():
        raise FileNotFoundError(f"Directorio fuente no existe: {src}")

    extra_excludes: frozenset[str] = frozenset(
        p.lower() for p in (exclude_patterns or [])
    )

    out_zip = Path(output_zip_path)
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    included: list[str] = []

    with zipfile.ZipFile(str(out_zip), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(src.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(src)
            parts = tuple(p.lower() for p in rel.parts)
            if _should_exclude(parts):
                continue
            if extra_excludes and any(p in extra_excludes for p in parts):
                continue
            arcname = rel.as_posix()
            zf.write(str(file_path), arcname)
            included.append(arcname)

    return included


# ---------------------------------------------------------------------------
# Conversores PDF
# ---------------------------------------------------------------------------

def convert_docx_to_pdf_with_soffice(
    docx_path: "str | Path",
    output_pdf_path: "str | Path",
    soffice_path: "str | None" = None,
    timeout_seconds: int = 120,
) -> bool:
    """
    Convierte DOCX a PDF usando LibreOffice/soffice.
    Devuelve True si el PDF se genero correctamente, False en caso contrario.
    No lanza salvo errores graves de ruta.
    """
    docx = Path(docx_path).resolve()
    out_pdf = Path(output_pdf_path).resolve()

    if not docx.exists():
        return False

    exe = soffice_path or find_soffice_executable()
    if not exe:
        return False

    out_dir = out_pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.run(
            [exe, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(docx)],
            capture_output=True,
            timeout=timeout_seconds,
        )
        if proc.returncode != 0:
            return False
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError, Exception):
        return False

    # LibreOffice crea <stem>.pdf en out_dir; mover si el nombre difiere
    soffice_out = out_dir / (docx.stem + ".pdf")
    if soffice_out.exists() and soffice_out != out_pdf:
        try:
            shutil.move(str(soffice_out), str(out_pdf))
        except OSError:
            return False

    return out_pdf.exists() and out_pdf.stat().st_size > 0


def convert_docx_to_pdf_with_word_com(
    docx_path: "str | Path",
    output_pdf_path: "str | Path",
) -> bool:
    """
    Convierte DOCX a PDF usando Microsoft Word via COM (Windows solo).
    Devuelve True si el PDF se genero, False si win32com no esta disponible o falla.
    Garantiza que Word no queda abierto aunque falle.
    """
    try:
        import win32com.client
    except (ImportError, Exception):
        return False

    docx = Path(docx_path).resolve()
    out_pdf = Path(output_pdf_path).resolve()

    if not docx.exists():
        return False

    word = None
    doc = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(str(docx))
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        doc.SaveAs(str(out_pdf), FileFormat=17)  # 17 = wdFormatPDF
        return out_pdf.exists() and out_pdf.stat().st_size > 0
    except Exception:
        return False
    finally:
        try:
            if doc is not None:
                doc.Close()
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Exportacion PDF best-effort
# ---------------------------------------------------------------------------

def export_pdf_best_effort(
    docx_path: "str | Path",
    output_pdf_path: "str | Path",
    prefer: str = "soffice",
) -> "tuple[str, list[ExportIssue]]":
    """
    Intenta generar un PDF del DOCX con el mejor conversor disponible.

    Devuelve (pdf_status, issues):
      - GENERATED si tuvo exito.
      - SOURCE_MISSING si el DOCX fuente no existe.
      - SKIPPED_NO_CONVERTER si no hay conversor disponible.
      - FAILED si el conversor existe pero falla.
    """
    docx = Path(docx_path)
    issues: list[ExportIssue] = []

    if not docx.exists():
        issues.append(ExportIssue(
            severity=EXPORT_SEVERITY.WARNING,
            code="EXP-W001",
            message=f"DOCX fuente no encontrado: {docx.name}",
            recommendation="Ejecute document-insert-figures --write o document-build-docx --write.",
            evidence=[str(docx)],
        ))
        return PDF_EXPORT_STATUS.SOURCE_MISSING, issues

    soffice = find_soffice_executable()
    word_com = can_use_word_com()

    converters = []
    if prefer == "soffice":
        if soffice:
            converters.append(("soffice", soffice))
        if word_com:
            converters.append(("word_com", None))
    else:
        if word_com:
            converters.append(("word_com", None))
        if soffice:
            converters.append(("soffice", soffice))

    if not converters:
        issues.append(ExportIssue(
            severity=EXPORT_SEVERITY.WARNING,
            code="EXP-W002",
            message="No se encontro conversor PDF (LibreOffice/soffice ni Word COM).",
            recommendation=(
                "Instale LibreOffice (https://www.libreoffice.org) o asegurese de que "
                "Microsoft Word esta disponible en Windows con pywin32 instalado."
            ),
            evidence=[],
        ))
        return PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER, issues

    # Intentar con cada conversor disponible
    for conv_name, conv_path in converters:
        if conv_name == "soffice":
            ok = convert_docx_to_pdf_with_soffice(docx, output_pdf_path, soffice_path=conv_path)
        else:
            ok = convert_docx_to_pdf_with_word_com(docx, output_pdf_path)
        if ok:
            return PDF_EXPORT_STATUS.GENERATED, issues

    # Conversor existe pero fallo
    issues.append(ExportIssue(
        severity=EXPORT_SEVERITY.WARNING,
        code="EXP-W003",
        message="El conversor PDF fallo. El ZIP sigue siendo valido.",
        recommendation="Revisar instalacion de LibreOffice o Microsoft Word.",
        evidence=[str(docx_path)],
    ))
    return PDF_EXPORT_STATUS.FAILED, issues


# ---------------------------------------------------------------------------
# Generadores de texto
# ---------------------------------------------------------------------------

def build_export_report_markdown(result: DocumentExportResult) -> str:
    """Genera el informe de exportacion en formato Markdown."""
    zip_label = "GENERADO" if result.zip_generated else "NO_GENERADO"
    lines: list[str] = [
        "# Resultado de exportacion documental",
        "",
        f"**Expediente:** {result.expediente_id}",
        f"**ZIP:** {zip_label}",
        f"**PDF:** {result.pdf_status}",
        f"**Archivos en ZIP:** {result.files_zipped_count()}",
        f"**Errores:** {result.error_count()}",
        f"**Advertencias:** {result.warning_count()}",
        "",
        "---",
        "",
        "## 1. Resumen",
        "",
    ]

    if result.is_success():
        lines.append(
            "La exportacion se ha completado correctamente. "
            "El ZIP esta listo para revision tecnica."
        )
    elif result.zip_generated:
        lines.append(
            "El ZIP se ha generado pero se han detectado incidencias. "
            "Revisar la lista de errores antes de usar el paquete."
        )
    else:
        lines.append(
            "El ZIP no se ha generado. Revisar que documento/paquete_entrega/ "
            "existe y ejecutar document-package --write primero."
        )

    lines += [
        "",
        "## 2. ZIP generado",
        "",
        f"**Ruta:** `{result.zip_path or 'N/A'}`",
        f"**Estado:** {zip_label}",
        f"**Archivos incluidos:** {result.files_zipped_count()}",
        "",
    ]

    lines += [
        "## 3. PDF generado",
        "",
        f"**Estado:** {result.pdf_status}",
        f"**DOCX fuente:** `{result.pdf_source_docx or 'N/A'}`",
        f"**PDF ruta:** `{result.pdf_path or 'N/A'}`",
        "",
    ]

    lines += [
        "## 4. Archivos incluidos en ZIP",
        "",
    ]
    if result.files_zipped:
        for f in result.files_zipped:
            lines.append(f"- `{f}`")
    else:
        lines.append("_Sin archivos en ZIP._")

    lines += [
        "",
        "## 5. Incidencias",
        "",
    ]
    if result.issues:
        for issue in result.issues:
            lines.append(f"- {issue.summary()}")
            if issue.recommendation:
                lines.append(f"  - Recomendacion: {issue.recommendation}")
    else:
        lines.append("_Sin incidencias._")

    lines += [
        "",
        "## 6. Advertencias",
        "",
    ]
    if result.warnings:
        for w in result.warnings:
            lines.append(f"- {w}")
    else:
        lines.append("_Sin advertencias adicionales._")

    lines += [
        "",
        "## 7. Advertencia de alcance",
        "",
        "> **Esta exportacion no declara el expediente apto para presentacion administrativa.**",
        "> Debe ser revisado por tecnico competente antes de su uso.",
        "> El presente paquete es un borrador de trabajo para revision tecnica interna.",
        "> La presentacion administrativa requiere firma y validacion tecnica/juridica completa.",
        "",
    ]

    return "\n".join(lines)


def write_export_result_outputs(
    result: DocumentExportResult,
    output_dir: "str | Path",
) -> "tuple[Path, Path]":
    """
    Escribe document_export_result.json y document_export_result.md.
    Devuelve (path_json, path_md).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / EXPORT_RESULT_JSON
    md_path = out / EXPORT_RESULT_MD

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

    md_path.write_text(build_export_report_markdown(result), encoding="utf-8")

    return json_path, md_path


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

def export_document_package(
    expediente_path: "str | Path",
    write_outputs: bool = False,
    generate_pdf: bool = True,
    overwrite: bool = True,
) -> DocumentExportResult:
    """
    Exporta el paquete documental final a ZIP y opcionalmente a PDF.

    Si write_outputs=False (default): solo analiza, no escribe nada.
    Si write_outputs=True:
      - Crea documento/paquete_entrega.zip con el contenido de paquete_entrega/.
      - Intenta generar PDF si generate_pdf=True y hay conversor disponible.
      - El ZIP no contiene el propio ZIP ni el PDF (ambos estan en documento/, fuera del paquete).

    No modifica paquete_entrega/, no modifica el DOCX fuente, no declara aptitud administrativa.
    """
    exp = Path(expediente_path)
    expediente_id = exp.name
    doc_dir = exp / "documento"
    package_dir = doc_dir / "paquete_entrega"
    zip_out = doc_dir / PACKAGE_ZIP_FILENAME
    docx_source = exp / DEFAULT_DOCX_SOURCE
    pdf_out = doc_dir / PDF_OUTPUT_FILENAME

    issues: list[ExportIssue] = []
    warnings: list[str] = []

    # Verificar que paquete_entrega/ existe
    if not package_dir.exists():
        issues.append(ExportIssue(
            severity=EXPORT_SEVERITY.ERROR,
            code="EXP-E001",
            message="No se encontro documento/paquete_entrega/.",
            recommendation=(
                "Ejecute primero: document-package --write "
                "para generar el paquete de entrega."
            ),
            evidence=[str(package_dir)],
        ))
        return DocumentExportResult(
            expediente_id=expediente_id,
            package_dir=None,
            zip_path=None,
            pdf_source_docx=str(docx_source),
            pdf_path=None,
            zip_generated=False,
            pdf_status=PDF_EXPORT_STATUS.NOT_REQUESTED if not generate_pdf
                       else (PDF_EXPORT_STATUS.SOURCE_MISSING if not docx_source.exists()
                             else PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER),
            files_zipped=[],
            issues=issues,
            warnings=warnings,
            notes=["ERROR: paquete_entrega/ no existe. ZIP no generado."],
        )

    # Dry-run: calcular lo que se haría sin escribir
    if not write_outputs:
        # Pre-listar archivos que entrarian en el ZIP
        would_zip: list[str] = []
        for fp in sorted(package_dir.rglob("*")):
            if not fp.is_file():
                continue
            rel = fp.relative_to(package_dir)
            parts = tuple(p.lower() for p in rel.parts)
            if not _should_exclude(parts):
                would_zip.append(rel.as_posix())

        # Determinar estado PDF sin ejecutar
        if not generate_pdf:
            dry_pdf_status = PDF_EXPORT_STATUS.NOT_REQUESTED
        elif not docx_source.exists():
            dry_pdf_status = PDF_EXPORT_STATUS.SOURCE_MISSING
        else:
            soffice = find_soffice_executable()
            word_com = can_use_word_com()
            if soffice or word_com:
                dry_pdf_status = PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER
                warnings.append(
                    "Dry-run: conversor disponible pero PDF no generado. "
                    "Use --write para exportar."
                )
            else:
                dry_pdf_status = PDF_EXPORT_STATUS.SKIPPED_NO_CONVERTER

        return DocumentExportResult(
            expediente_id=expediente_id,
            package_dir=str(package_dir),
            zip_path=str(zip_out),
            pdf_source_docx=str(docx_source),
            pdf_path=str(pdf_out) if generate_pdf else None,
            zip_generated=False,
            pdf_status=dry_pdf_status,
            files_zipped=would_zip,
            issues=issues,
            warnings=warnings,
            notes=[
                "Modo dry-run: no se ha creado ZIP ni PDF.",
                "Use write_outputs=True para generar.",
            ],
        )

    # Modo escritura: crear ZIP
    if overwrite and zip_out.exists():
        zip_out.unlink()

    try:
        files_zipped = create_zip_from_directory(package_dir, zip_out)
        zip_generated = True
    except Exception as exc:
        issues.append(ExportIssue(
            severity=EXPORT_SEVERITY.ERROR,
            code="EXP-E002",
            message=f"Error creando ZIP: {exc}",
            recommendation="Verificar permisos de escritura en documento/.",
            evidence=[str(package_dir), str(zip_out)],
        ))
        return DocumentExportResult(
            expediente_id=expediente_id,
            package_dir=str(package_dir),
            zip_path=None,
            pdf_source_docx=str(docx_source),
            pdf_path=None,
            zip_generated=False,
            pdf_status=PDF_EXPORT_STATUS.NOT_REQUESTED,
            files_zipped=[],
            issues=issues,
            warnings=warnings,
            notes=["Error al crear ZIP."],
        )

    # Exportacion PDF best-effort
    pdf_status = PDF_EXPORT_STATUS.NOT_REQUESTED
    pdf_path_str = None

    if generate_pdf:
        pdf_status, pdf_issues = export_pdf_best_effort(docx_source, pdf_out)
        issues.extend(pdf_issues)
        if pdf_status == PDF_EXPORT_STATUS.GENERATED:
            pdf_path_str = str(pdf_out)

    return DocumentExportResult(
        expediente_id=expediente_id,
        package_dir=str(package_dir),
        zip_path=str(zip_out),
        pdf_source_docx=str(docx_source),
        pdf_path=pdf_path_str,
        zip_generated=zip_generated,
        pdf_status=pdf_status,
        files_zipped=files_zipped,
        issues=issues,
        warnings=warnings,
        notes=[
            "Este paquete no declara aptitud para presentacion administrativa.",
            "Revisar con tecnico competente antes de cualquier uso.",
        ],
    )
