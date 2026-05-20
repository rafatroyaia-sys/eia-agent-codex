"""
document_quality_checker -- DOC-04
Control de calidad del paquete documental final.

Verifica que el paquete generado (DOC-00 a DOC-03) esta completo
y es revisable antes de la revision tecnica/juridica.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica DOCX ni Markdown fuente.
  - No genera PDF.
  - No declara aptitud administrativa.
  - No modifica impactos, medidas, PVA ni auditorias.
  - Solo lee; no escribe salvo --write.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes publicas
# ---------------------------------------------------------------------------

DOCUMENT_QC_STATUS: list[str] = [
    "OK",
    "CON_OBSERVACIONES",
    "NO_CONFORME",
    "SIN_DATOS",
]

DOCUMENT_QC_SEVERITY: list[str] = [
    "ERROR",
    "WARNING",
    "INFO",
]

# Archivos obligatorios del paquete documental (rutas relativas al expediente)
REQUIRED_DOCUMENT_FILES: list[str] = [
    "documento/document_manifest.json",
    "documento/document_manifest.md",
    "documento/documento_ambiental_borrador.md",
    "documento/document_build_result.json",
    "documento/documento_ambiental_borrador.docx",
    "documento/docx_build_result.json",
]

# Archivos opcionales del DOCX enriquecido (DOC-03)
OPTIONAL_ENRICHED_FILES: list[str] = [
    "documento/documento_ambiental_borrador_con_figuras.docx",
    "documento/document_figures_result.json",
    "documento/document_figures_result.md",
]

# Archivos de auditoria final
AUDIT_FILES: list[str] = [
    "auditoria/final_audit_result.json",
    "auditoria/final_audit_result.md",
]

REQUIRED_BLOCKS: list[str] = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]

_QC_SEVERITY_ORDER = {s: i for i, s in enumerate(DOCUMENT_QC_SEVERITY)}

# Severidad por archivo requerido
_REQUIRED_FILE_SEVERITY: dict[str, str] = {
    "documento/documento_ambiental_borrador.docx": "ERROR",
    "documento/documento_ambiental_borrador.md": "ERROR",
    "documento/document_manifest.json": "WARNING",
    "documento/document_manifest.md": "INFO",
    "documento/document_build_result.json": "WARNING",
    "documento/docx_build_result.json": "WARNING",
}

# Frases prohibidas (declaracion implicita de aptitud administrativa)
_PROHIBITED_ADMIN_PHRASES: list[str] = [
    "apto administrativamente",
    "apto para presentacion administrativa",
    "expediente apto",
    "conforme para presentar",
    "sin condicionantes",
    "listo para presentar",
    "validado administrativamente",
]
_NEGATION_MARKERS: list[str] = ["no ", "no\t", "no\n", "nunca ", "tampoco ", "sin ser "]
_NEGATION_WINDOW = 15


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _normalize_text(s: str) -> str:
    """Minusculas + elimina tildes/diacriticos para comparacion tolerante."""
    s = s.lower()
    s = unicodedata.normalize("NFKD", s)
    return s.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DocumentQualityIssue:
    """Una incidencia detectada durante el control de calidad documental."""

    severity: str
    code: str
    file_path: "str | None"
    message: str
    recommendation: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "file_path": self.file_path,
            "message": self.message,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }

    def summary(self) -> str:
        fp = f" [{self.file_path}]" if self.file_path else ""
        return f"[{self.severity}][{self.code}]{fp} {self.message}"


@dataclass
class DocumentQualityResult:
    """Resultado completo del control de calidad documental."""

    expediente_id: str
    status: str
    checked_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    docx_path_checked: "str | None" = None
    blocks_found: list[str] = field(default_factory=list)
    blocks_missing: list[str] = field(default_factory=list)
    figures_found: list[str] = field(default_factory=list)
    captions_found: list[str] = field(default_factory=list)
    issues: list[DocumentQualityIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "INFO")

    def is_valid(self) -> bool:
        """True si no hay ERRORs."""
        return self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "checked_files": self.checked_files,
            "missing_files": self.missing_files,
            "docx_path_checked": self.docx_path_checked,
            "blocks_found": self.blocks_found,
            "blocks_missing": self.blocks_missing,
            "figures_found": self.figures_found,
            "captions_found": self.captions_found,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": self.warnings,
            "notes": self.notes,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
        }

    def summary(self) -> str:
        lines = [
            f"Control de calidad: {self.status}",
            f"  Errores: {self.error_count()}  Advertencias: {self.warning_count()}  "
            f"Info: {self.info_count()}",
            f"  Archivos revisados: {len(self.checked_files)}  "
            f"Faltantes: {len(self.missing_files)}",
            f"  Bloques A-K: {len(self.blocks_found)}/11  "
            f"Figuras: {len(self.figures_found)}  Captions: {len(self.captions_found)}",
        ]
        if not self.is_valid():
            lines.append(
                "  RESULTADO: NO VALIDO (hay ERRORs que deben resolverse antes de revision)"
            )
        else:
            lines.append("  RESULTADO: VALIDO (sin ERRORs)")
        lines.append(
            "  AVISO: Este QC no declara el expediente apto para presentacion administrativa."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Funciones de soporte
# ---------------------------------------------------------------------------

def safe_load_json(path: "str | Path") -> "dict | list | None":
    """Carga JSON de forma segura. Devuelve None si no existe o esta corrupto."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def select_best_docx_for_qc(expediente_path: "str | Path") -> "Path | None":
    """
    Elige el mejor DOCX para la revision de calidad.
    Preferencia: DOCX enriquecido con figuras > DOCX base > None.
    """
    exp = Path(expediente_path)
    enriched = exp / "documento" / "documento_ambiental_borrador_con_figuras.docx"
    base = exp / "documento" / "documento_ambiental_borrador.docx"
    if enriched.exists():
        return enriched
    if base.exists():
        return base
    return None


def validate_docx_opens(path: "str | Path") -> bool:
    """True si el archivo existe, tiene tamano >0 y python-docx puede abrirlo."""
    p = Path(path)
    if not p.exists():
        return False
    if p.stat().st_size == 0:
        return False
    try:
        from docx import Document as _Doc
        _Doc(str(p))
        return True
    except Exception:
        return False


def extract_docx_text(path: "str | Path") -> str:
    """
    Extrae texto de paragrafos y tablas del DOCX.
    Devuelve cadena vacia si falla.
    """
    try:
        from docx import Document as _Doc
        doc = _Doc(str(path))
        parts: list[str] = []
        for para in doc.paragraphs:
            t = para.text.strip()
            if t:
                parts.append(t)
        for table in doc.tables:
            for row in table.rows:
                row_text = "\t".join(c.text.strip() for c in row.cells)
                if row_text.strip():
                    parts.append(row_text)
        return "\n".join(parts)
    except Exception:
        return ""


def detect_blocks_in_text(text: str) -> list[str]:
    """
    Detecta bloques A-K en texto de DOCX/Markdown.
    Tolerante a: "A —", "## A", "Bloque A", "A. Identificacion".
    """
    found: set[str] = set()
    for block in REQUIRED_BLOCKS:
        b = re.escape(block)
        patterns = [
            rf"(?m)^#*\s*{b}\s*[—–\-\.:]",   # "# A —", "A —", "A."
            rf"(?i)\bbloque\s+{b}\b",               # "Bloque A"
            rf"(?m)^{b}\s+[A-ZÀ-ɏ]",     # "A Identificacion"
        ]
        for pat in patterns:
            if re.search(pat, text):
                found.add(block)
                break
    return sorted(found)


# ---------------------------------------------------------------------------
# Funciones de verificacion
# ---------------------------------------------------------------------------

def check_required_document_files(
    expediente_path: "str | Path",
) -> list[DocumentQualityIssue]:
    """
    Verifica existencia de archivos requeridos del paquete documental.
    DOCX base y Markdown → ERROR si faltan.
    Manifest, build results → WARNING.
    Archivos opcionales enriquecidos → INFO o WARNING segun contexto.
    """
    issues: list[DocumentQualityIssue] = []
    exp = Path(expediente_path)

    for rel in REQUIRED_DOCUMENT_FILES:
        full = exp / rel
        if not full.exists():
            sev = _REQUIRED_FILE_SEVERITY.get(rel, "WARNING")
            issues.append(DocumentQualityIssue(
                severity=sev,
                code="QC-E001" if sev == "ERROR" else "QC-W001",
                file_path=rel,
                message=f"Archivo requerido no encontrado: {rel}",
                recommendation=_file_recommendation(rel),
                evidence=[f"Path esperado: {full}"],
            ))

    # Archivos opcionales del DOCX enriquecido
    figs_result_path = exp / "documento" / "document_figures_result.json"
    enriched_docx = exp / "documento" / "documento_ambiental_borrador_con_figuras.docx"
    figs_data = safe_load_json(figs_result_path)

    if figs_data is not None and figs_data.get("generated") is True:
        if not enriched_docx.exists():
            issues.append(DocumentQualityIssue(
                severity="WARNING",
                code="QC-W001",
                file_path="documento/documento_ambiental_borrador_con_figuras.docx",
                message=(
                    "document_figures_result.json indica generated=True "
                    "pero el DOCX enriquecido no existe."
                ),
                recommendation="Ejecutar 'document-insert-figures --write' de nuevo.",
                evidence=["document_figures_result.json: generated=True"],
            ))
    elif not enriched_docx.exists():
        issues.append(DocumentQualityIssue(
            severity="INFO",
            code="QC-I001",
            file_path="documento/documento_ambiental_borrador_con_figuras.docx",
            message="DOCX enriquecido con figuras no existe (DOC-03 no ejecutado).",
            recommendation="Opcional: ejecutar 'document-insert-figures [--write]'.",
            evidence=[],
        ))

    return issues


def _file_recommendation(rel: str) -> str:
    table = {
        "documento/documento_ambiental_borrador.docx": "Ejecutar 'document-build-docx --write'.",
        "documento/documento_ambiental_borrador.md": "Ejecutar 'document-build-md --write'.",
        "documento/document_manifest.json": "Ejecutar 'document-manifest --write'.",
        "documento/document_manifest.md": "Ejecutar 'document-manifest --write'.",
        "documento/document_build_result.json": "Ejecutar 'document-build-md --write'.",
        "documento/docx_build_result.json": "Ejecutar 'document-build-docx --write'.",
    }
    return table.get(rel, "Verificar que el paso correspondiente se ejecuto correctamente.")


def check_docx_structure(
    expediente_path: "str | Path",
) -> list[DocumentQualityIssue]:
    """
    Verifica estructura interna del DOCX: disclaimer, indices, bloques A-K.
    """
    issues: list[DocumentQualityIssue] = []
    exp = Path(expediente_path)

    docx_path = select_best_docx_for_qc(exp)
    if docx_path is None:
        issues.append(DocumentQualityIssue(
            severity="ERROR",
            code="QC-E001",
            file_path=None,
            message="No se encontro ningun DOCX para revisar la estructura.",
            recommendation="Ejecutar 'document-build-docx --write'.",
            evidence=[],
        ))
        return issues

    if not validate_docx_opens(docx_path):
        issues.append(DocumentQualityIssue(
            severity="ERROR",
            code="QC-E002",
            file_path=str(docx_path),
            message="El DOCX no se puede abrir con python-docx.",
            recommendation="Regenerar el DOCX ejecutando 'document-build-docx --write'.",
            evidence=[],
        ))
        return issues

    text = extract_docx_text(docx_path)
    norm = _normalize_text(text)

    # Disclaimer de no aptitud
    if "no declara aptitud administrativa" not in norm:
        issues.append(DocumentQualityIssue(
            severity="ERROR",
            code="QC-E004",
            file_path=str(docx_path),
            message="El DOCX no contiene la advertencia 'No declara aptitud administrativa'.",
            recommendation=(
                "Verificar que DOC-01 incluye el disclaimer. "
                "Regenerar Markdown y DOCX."
            ),
            evidence=["Cadena 'no declara aptitud administrativa' no encontrada."],
        ))

    # Indice / TOC placeholder
    if not re.search(r"(tabla de contenidos|indice|contenido)", norm):
        issues.append(DocumentQualityIssue(
            severity="WARNING",
            code="QC-W002",
            file_path=str(docx_path),
            message="No se detecto indice o tabla de contenidos en el DOCX.",
            recommendation=(
                "Verificar que DOC-02 incluye placeholder de indice. "
                "Actualizar TOC con Ctrl+A > F9 en Word."
            ),
            evidence=[],
        ))

    # Bloques A-K
    blocks_found = detect_blocks_in_text(text)
    for block in REQUIRED_BLOCKS:
        if block not in blocks_found:
            issues.append(DocumentQualityIssue(
                severity="ERROR",
                code="QC-E003",
                file_path=str(docx_path),
                message=f"Bloque {block} no encontrado en el DOCX.",
                recommendation=(
                    f"Verificar que DOC-01 genero el bloque {block}. "
                    "Regenerar Markdown y DOCX."
                ),
                evidence=[f"Bloque {block} ausente en texto extraido del DOCX."],
            ))

    # Bloque G parcial
    build_result = safe_load_json(exp / "documento" / "document_build_result.json")
    if isinstance(build_result, dict):
        for br in build_result.get("block_results", []):
            if isinstance(br, dict) and br.get("block_id") == "G" and br.get("status") == "PARTIAL":
                issues.append(DocumentQualityIssue(
                    severity="WARNING",
                    code="QC-W006",
                    file_path="documento/document_build_result.json",
                    message=(
                        "Bloque G (Alternativas y justificacion) tiene estado PARTIAL "
                        "en document_build_result.json."
                    ),
                    recommendation=(
                        "El modo gabinete limita la generacion de alternativas. "
                        "Revisar contenido del bloque G antes de la revision."
                    ),
                    evidence=["block_results[G].status = PARTIAL"],
                ))
                break

    return issues


def check_figures_and_captions(
    expediente_path: "str | Path",
) -> list[DocumentQualityIssue]:
    """
    Verifica coherencia entre document_figures_result.json y captions en DOCX.
    """
    issues: list[DocumentQualityIssue] = []
    exp = Path(expediente_path)
    figs_path = exp / "documento" / "document_figures_result.json"
    figs_data = safe_load_json(figs_path)

    if figs_data is None:
        issues.append(DocumentQualityIssue(
            severity="WARNING",
            code="QC-W003",
            file_path=str(figs_path),
            message="No se encontro document_figures_result.json (DOC-03 no ejecutado).",
            recommendation="Opcional: ejecutar 'document-insert-figures --write'.",
            evidence=[],
        ))
        return issues

    figures_inserted: list[str] = figs_data.get("figures_inserted", [])
    figures_skipped: list = figs_data.get("figures_skipped", [])
    generated: bool = bool(figs_data.get("generated", False))

    if figures_skipped:
        issues.append(DocumentQualityIssue(
            severity="WARNING",
            code="QC-W004",
            file_path=str(figs_path),
            message=f"{len(figures_skipped)} figura(s) omitidas durante la insercion.",
            recommendation="Revisar las figuras omitidas: pueden estar corruptas o no ser imagenes validas.",
            evidence=[str(figures_skipped)],
        ))

    if not figures_inserted:
        issues.append(DocumentQualityIssue(
            severity="WARNING",
            code="QC-W003",
            file_path=str(figs_path),
            message="No hay figuras insertadas en el paquete documental.",
            recommendation="Verificar que existen imagenes en los directorios del expediente.",
            evidence=[],
        ))
        return issues

    enriched_docx = exp / "documento" / "documento_ambiental_borrador_con_figuras.docx"
    if generated and not enriched_docx.exists():
        issues.append(DocumentQualityIssue(
            severity="ERROR",
            code="QC-E005",
            file_path="documento/documento_ambiental_borrador_con_figuras.docx",
            message=(
                "document_figures_result.json indica generated=True "
                "pero el DOCX enriquecido no se encuentra."
            ),
            recommendation="Ejecutar 'document-insert-figures --write' de nuevo.",
            evidence=[f"figures_inserted={figures_inserted}"],
        ))
        return issues

    if not enriched_docx.exists():
        return issues

    docx_text = extract_docx_text(enriched_docx)
    for fig_id in figures_inserted:
        if fig_id not in docx_text:
            issues.append(DocumentQualityIssue(
                severity="ERROR",
                code="QC-E005",
                file_path=str(enriched_docx),
                message=f"Caption '{fig_id}' no encontrado en el DOCX enriquecido.",
                recommendation="Regenerar el DOCX enriquecido con 'document-insert-figures --write'.",
                evidence=[f"figures_inserted contiene {fig_id} pero no aparece en DOCX."],
            ))

    return issues


def check_final_audit_visibility(
    expediente_path: "str | Path",
) -> list[DocumentQualityIssue]:
    """
    Verifica que el estado de la auditoria final es visible en el documento
    y que ningun JSON declara administrative_ready=True.
    """
    issues: list[DocumentQualityIssue] = []
    exp = Path(expediente_path)

    audit_json_path = exp / "auditoria" / "final_audit_result.json"
    audit_data = safe_load_json(audit_json_path)

    if audit_data is None:
        issues.append(DocumentQualityIssue(
            severity="WARNING",
            code="QC-W005",
            file_path=str(audit_json_path),
            message="No se encontro auditoria/final_audit_result.json.",
            recommendation=(
                "Verificar que el pipeline tecnico completo se ha ejecutado. "
                "Ejecutar 'run-technical-pipeline --write'."
            ),
            evidence=[],
        ))
    else:
        # Verificar administrative_ready
        if audit_data.get("administrative_ready") is True:
            issues.append(DocumentQualityIssue(
                severity="ERROR",
                code="QC-E007",
                file_path=str(audit_json_path),
                message="auditoria/final_audit_result.json declara administrative_ready=True.",
                recommendation=(
                    "administrative_ready debe ser False. "
                    "Este sistema no declara aptitud administrativa."
                ),
                evidence=["administrative_ready: true en final_audit_result.json"],
            ))

        # Verificar visibilidad de NO_CONFORME
        audit_status = audit_data.get("status") or audit_data.get("final_audit_status", "")
        if audit_status == "NO_CONFORME":
            docx_path = select_best_docx_for_qc(exp)
            md_path = exp / "documento" / "documento_ambiental_borrador.md"
            visible = False

            if docx_path and docx_path.exists():
                docx_text = _normalize_text(extract_docx_text(docx_path))
                if any(kw in docx_text for kw in ["no conforme", "noconforme", "observacion", "con observaciones"]):
                    visible = True

            if not visible and md_path.exists():
                try:
                    md_text = _normalize_text(md_path.read_text(encoding="utf-8"))
                    if any(kw in md_text for kw in ["no conforme", "noconforme", "observacion", "con observaciones"]):
                        visible = True
                except Exception:
                    pass

            if not visible:
                issues.append(DocumentQualityIssue(
                    severity="ERROR",
                    code="QC-E006",
                    file_path=str(audit_json_path),
                    message=(
                        "La auditoria final es NO_CONFORME pero el documento "
                        "no refleja esta advertencia."
                    ),
                    recommendation=(
                        "Verificar que DOC-01 incluye el estado de la auditoria. "
                        "Regenerar Markdown y DOCX."
                    ),
                    evidence=[f"audit_status={audit_status}"],
                ))

    # Verificar administrative_ready en otros JSONs del paquete
    for rel in ["documento/docx_build_result.json", "documento/document_build_result.json"]:
        data = safe_load_json(exp / rel)
        if isinstance(data, dict) and data.get("administrative_ready") is True:
            issues.append(DocumentQualityIssue(
                severity="ERROR",
                code="QC-E007",
                file_path=rel,
                message=f"{rel} declara administrative_ready=True.",
                recommendation="administrative_ready debe ser False en todos los outputs.",
                evidence=[f"administrative_ready: true en {rel}"],
            ))

    return issues


def check_no_administrative_ready_claim(text: str) -> list[DocumentQualityIssue]:
    """
    Detecta frases que declaren aptitud administrativa en el texto del documento.
    Respeta frases negativas como 'no declara aptitud administrativa'.
    """
    issues: list[DocumentQualityIssue] = []
    norm = _normalize_text(text)
    seen_codes: set[str] = set()

    for phrase in _PROHIBITED_ADMIN_PHRASES:
        pos = 0
        while True:
            idx = norm.find(phrase, pos)
            if idx < 0:
                break
            window_start = max(0, idx - _NEGATION_WINDOW)
            window = norm[window_start:idx]
            negated = any(m in window for m in _NEGATION_MARKERS)
            if not negated and phrase not in seen_codes:
                seen_codes.add(phrase)
                issues.append(DocumentQualityIssue(
                    severity="ERROR",
                    code="QC-E008",
                    file_path=None,
                    message=f"Frase prohibida detectada en el documento: '{phrase}'.",
                    recommendation=(
                        "Eliminar la declaracion implicita de aptitud administrativa. "
                        "Usar: 'No declara aptitud administrativa'."
                    ),
                    evidence=[f"Frase encontrada: '{phrase}'"],
                ))
            pos = idx + 1

    return issues


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

def run_document_quality_check(
    expediente_path: "str | Path",
) -> DocumentQualityResult:
    """
    Ejecuta todos los checks de calidad documental.
    No modifica ningun archivo del expediente.
    """
    exp = Path(expediente_path)
    expediente_id = exp.name

    all_issues: list[DocumentQualityIssue] = []

    # 1. Archivos requeridos
    all_issues.extend(check_required_document_files(exp))

    # 2. Estructura DOCX
    all_issues.extend(check_docx_structure(exp))

    # 3. Figuras y captions
    all_issues.extend(check_figures_and_captions(exp))

    # 4. Auditoria final
    all_issues.extend(check_final_audit_visibility(exp))

    # 5. Frases prohibidas en DOCX
    docx_path = select_best_docx_for_qc(exp)
    docx_text = extract_docx_text(docx_path) if docx_path else ""
    all_issues.extend(check_no_administrative_ready_claim(docx_text))

    # Recopilar informacion de diagnostico
    checked: list[str] = []
    missing: list[str] = []
    for rel in REQUIRED_DOCUMENT_FILES + OPTIONAL_ENRICHED_FILES + AUDIT_FILES:
        full = exp / rel
        if full.exists():
            checked.append(rel)
        else:
            missing.append(rel)

    blocks_found = detect_blocks_in_text(docx_text) if docx_text else []
    blocks_missing = [b for b in REQUIRED_BLOCKS if b not in blocks_found]

    # Figuras y captions desde JSON
    figs_data = safe_load_json(exp / "documento" / "document_figures_result.json")
    figures_found: list[str] = []
    captions_found: list[str] = []
    if isinstance(figs_data, dict):
        figures_found = figs_data.get("figures_inserted", [])
        if docx_text:
            captions_found = [f for f in figures_found if f in docx_text]

    # Determinar status
    errors = [i for i in all_issues if i.severity == "ERROR"]
    warnings = [i for i in all_issues if i.severity == "WARNING"]
    n_missing_required = sum(
        1 for r in REQUIRED_DOCUMENT_FILES if not (exp / r).exists()
    )

    if n_missing_required >= 4:
        status = "SIN_DATOS"
    elif errors:
        status = "NO_CONFORME"
    elif warnings:
        status = "CON_OBSERVACIONES"
    else:
        status = "OK"

    notes = [
        "Este control de calidad no declara el expediente apto para presentacion administrativa.",
        "Solo verifica completitud y coherencia del paquete documental generado.",
    ]

    return DocumentQualityResult(
        expediente_id=expediente_id,
        status=status,
        checked_files=checked,
        missing_files=missing,
        docx_path_checked=str(docx_path) if docx_path else None,
        blocks_found=blocks_found,
        blocks_missing=blocks_missing,
        figures_found=figures_found,
        captions_found=captions_found,
        issues=all_issues,
        warnings=[i.summary() for i in all_issues if i.severity == "WARNING"],
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Generacion del informe Markdown
# ---------------------------------------------------------------------------

def build_document_quality_report_markdown(result: DocumentQualityResult) -> str:
    """Genera el informe de control de calidad en formato Markdown."""
    lines: list[str] = [
        "# Control de calidad del paquete documental",
        "",
        f"**Expediente:** {result.expediente_id}",
        f"**Estado:** {result.status}",
        f"**Errores:** {result.error_count()}  "
        f"**Advertencias:** {result.warning_count()}  "
        f"**Info:** {result.info_count()}",
        "",
        "---",
        "",
        "## 1. Resumen",
        "",
    ]

    if result.status == "OK":
        lines.append("El paquete documental ha superado el control de calidad sin incidencias.")
    elif result.status == "CON_OBSERVACIONES":
        lines.append(
            "El paquete documental presenta advertencias que deben revisarse antes de su uso."
        )
    elif result.status == "NO_CONFORME":
        lines.append(
            "El paquete documental presenta errores que **deben corregirse** antes de la revision."
        )
    else:
        lines.append(
            "Datos insuficientes para completar el control de calidad. "
            "Verificar que el pipeline documental se ha ejecutado."
        )

    lines += [
        "",
        "## 2. Archivos revisados",
        "",
        f"**Presentes:** {len(result.checked_files)}",
        f"**Faltantes:** {len(result.missing_files)}",
        "",
    ]
    if result.checked_files:
        for f in result.checked_files:
            lines.append(f"- {f}")
    lines.append("")

    lines += ["## 3. Archivos faltantes", ""]
    if result.missing_files:
        for f in result.missing_files:
            lines.append(f"- {f}")
    else:
        lines.append("_Sin archivos faltantes relevantes._")
    lines.append("")

    lines += ["## 4. Bloques A-K", ""]
    if result.blocks_found:
        found_str = ", ".join(result.blocks_found)
        missing_str = ", ".join(result.blocks_missing) if result.blocks_missing else "ninguno"
        lines.append(f"**Encontrados:** {found_str}")
        lines.append(f"**Faltantes:** {missing_str}")
    else:
        lines.append("No se pudo extraer informacion de bloques del DOCX.")
    lines.append("")

    lines += ["## 5. Figuras y captions", ""]
    if result.figures_found:
        lines.append(f"**Figuras insertadas:** {len(result.figures_found)}")
        lines.append(f"**Captions verificados en DOCX:** {len(result.captions_found)}")
        if result.figures_found:
            for fig in result.figures_found:
                state = "OK" if fig in result.captions_found else "FALTA CAPTION"
                lines.append(f"- {fig}: {state}")
    else:
        lines.append("_Sin figuras insertadas en el paquete._")
    lines.append("")

    lines += ["## 6. Auditoria final", ""]
    audit_issues = [i for i in result.issues if i.code in ("QC-E006", "QC-E007", "QC-W005")]
    if audit_issues:
        for issue in audit_issues:
            lines.append(f"- **[{issue.severity}]** {issue.message}")
    else:
        lines.append("Sin incidencias relacionadas con la auditoria final.")
    lines.append("")

    lines += ["## 7. Incidencias", ""]
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings_list = [i for i in result.issues if i.severity == "WARNING"]
    infos = [i for i in result.issues if i.severity == "INFO"]

    if errors:
        lines.append("### Errores")
        lines.append("")
        for issue in errors:
            lines.append(f"**[{issue.code}]** {issue.message}")
            if issue.recommendation:
                lines.append(f"  - *Recomendacion:* {issue.recommendation}")
            lines.append("")
    if warnings_list:
        lines.append("### Advertencias")
        lines.append("")
        for issue in warnings_list:
            lines.append(f"**[{issue.code}]** {issue.message}")
            if issue.recommendation:
                lines.append(f"  - *Recomendacion:* {issue.recommendation}")
            lines.append("")
    if infos:
        lines.append("### Informacion")
        lines.append("")
        for issue in infos:
            lines.append(f"**[{issue.code}]** {issue.message}")
            lines.append("")

    if not result.issues:
        lines.append("_Sin incidencias._")
        lines.append("")

    lines += ["## 8. Recomendaciones", ""]
    recs: list[str] = []
    for issue in result.issues:
        if issue.recommendation and issue.recommendation not in recs:
            recs.append(issue.recommendation)
    if recs:
        for rec in recs:
            lines.append(f"- {rec}")
    else:
        lines.append("_Sin recomendaciones adicionales._")
    lines.append("")

    lines += [
        "## 9. Advertencia de alcance",
        "",
        "> Este control de calidad no declara el expediente apto para presentacion "
        "administrativa.",
        "> El resultado de este QC es orientativo para la revision tecnica interna.",
        "> La presentacion administrativa requiere revision tecnica/juridica completa.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_document_quality_outputs(
    result: DocumentQualityResult,
    output_dir: "str | Path",
) -> "tuple[Path, Path]":
    """
    Escribe document_quality_result.json y document_quality_result.md.
    Devuelve (path_json, path_md).
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "document_quality_result.json"
    md_path = out / "document_quality_result.md"

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

    md_content = build_document_quality_report_markdown(result)
    md_path.write_text(md_content, encoding="utf-8")

    return json_path, md_path
