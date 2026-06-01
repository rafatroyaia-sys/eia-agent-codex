"""
document_flow_da.py — DA-01

Flujo completo de generacion del Documento Ambiental para expediente cliente.
Orquesta la cadena: pipeline tecnico -> cadena documental -> estado final.

Genera tres salidas:
  - documento/estado_expediente_da.json
  - documento/estado_expediente_da.md
  - (todos los outputs individuales de cada paso)

El informe de estado clasifica cada item en:
  CERRADO    — completado y validado (evidencia CONFIRMADO/DECLARADO, audit OK)
  PENDIENTE  — con datos parciales/inferidos (requiere revision o datos adicionales)
  BLOQUEANTE — fallo critico que impide presentacion administrativa

administrative_ready=False siempre. Este modulo no declara aptitud administrativa.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_STEP_NAMES = {
    "TECHNICAL_PIPELINE": "Pipeline tecnico (19 pasos: inventario -> auditorias)",
    "DOCUMENT_MANIFEST":  "Manifest del Documento Ambiental (bloques A-K)",
    "DOCUMENT_BUILD_MD":  "Generacion borrador Markdown",
    "DOCUMENT_BUILD_DOCX": "Conversion Markdown -> DOCX",
    "DOCUMENT_FIGURES":   "Insercion de figuras y mapas",
    "DOCUMENT_QC":        "Control de calidad documental (QC)",
    "DOCUMENT_PACKAGE":   "Empaquetado de entrega",
    "DOCUMENT_EXPORT":    "Exportacion ZIP",
    "DOCUMENT_PRESENTATION": "Preparacion para firma y presentacion",
    "DOCUMENT_STRUCTURE": "Validacion y normalizacion de estructura DOCX",
    "DOCUMENT_NUMBERING": "Aplicacion de estilos de numeracion",
    "DOCUMENT_TOC":       "Insercion de indice automatico (TOC)",
    "ESTADO_FINAL":       "Agregacion de estado final del expediente",
}

_RESULTADO_FLUJO_LABELS = {
    "FLUJO_COMPLETO":         "COMPLETO — todos los pasos OK, sin pendientes ni bloqueantes",
    "CERRADO_CON_PENDIENTES": "CERRADO CON PENDIENTES — flujo ejecutado, revisar items pendientes",
    "BLOQUEADO":              "BLOQUEADO — hay items que impiden la presentacion administrativa",
}

DISCLAIMER_DA = (
    "Este informe NO declara el expediente apto para presentacion administrativa. "
    "administrative_ready=False. Requiere revision tecnica y juridica del promotor."
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DAFlowStep:
    """Resultado de un paso del flujo DA-01."""
    step_id: str
    name: str
    status: str        # "OK", "WARNING", "FAILED", "SKIPPED"
    message: str = ""
    output_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def is_ok(self) -> bool:
        return self.status in ("OK", "WARNING")

    def is_warning(self) -> bool:
        return self.status == "WARNING"

    def is_failed(self) -> bool:
        return self.status in ("FAILED", "SKIPPED")

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "output_files": self.output_files,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class DAEstadoItem:
    """Un item clasificado en el informe de estado del expediente."""
    categoria: str   # "CERRADO", "PENDIENTE", "BLOQUEANTE"
    item: str
    fuente: str
    valor: str
    accion: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "categoria": self.categoria,
            "item": self.item,
            "fuente": self.fuente,
            "valor": self.valor,
        }
        if self.accion:
            d["accion"] = self.accion
        return d


@dataclass
class DAFlowResult:
    """Resultado completo del flujo DA-01."""
    expediente_id: str
    administrative_ready: bool
    resultado_flujo: str
    steps: list[DAFlowStep] = field(default_factory=list)
    estado_cerrado: list[DAEstadoItem] = field(default_factory=list)
    estado_pendiente: list[DAEstadoItem] = field(default_factory=list)
    estado_bloqueante: list[DAEstadoItem] = field(default_factory=list)

    def is_complete(self) -> bool:
        return self.resultado_flujo == "FLUJO_COMPLETO"

    def has_blocking(self) -> bool:
        return bool(self.estado_bloqueante)

    def count_by_categoria(self) -> dict[str, int]:
        return {
            "CERRADO":    len(self.estado_cerrado),
            "PENDIENTE":  len(self.estado_pendiente),
            "BLOQUEANTE": len(self.estado_bloqueante),
        }

    def steps_ok(self) -> int:
        return sum(1 for s in self.steps if s.is_ok())

    def steps_failed(self) -> int:
        return sum(1 for s in self.steps if s.is_failed())

    def summary(self) -> str:
        label = _RESULTADO_FLUJO_LABELS.get(self.resultado_flujo, self.resultado_flujo)
        counts = self.count_by_categoria()
        ok = self.steps_ok()
        total = len(self.steps)
        lines = [
            f"--- DA-01 Flujo Documento Ambiental [{self.expediente_id}] ---",
            f"Resultado    : {label}",
            f"Pasos OK     : {ok}/{total}",
            f"CERRADO      : {counts['CERRADO']}",
            f"PENDIENTE    : {counts['PENDIENTE']}",
            f"BLOQUEANTE   : {counts['BLOQUEANTE']}",
            f"Admin ready  : {self.administrative_ready}",
            f"NOTA: {DISCLAIMER_DA}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "administrative_ready": self.administrative_ready,
            "resultado_flujo": self.resultado_flujo,
            "resultado_flujo_label": _RESULTADO_FLUJO_LABELS.get(
                self.resultado_flujo, self.resultado_flujo
            ),
            "steps": [s.to_dict() for s in self.steps],
            "estado_cerrado": [i.to_dict() for i in self.estado_cerrado],
            "estado_pendiente": [i.to_dict() for i in self.estado_pendiente],
            "estado_bloqueante": [i.to_dict() for i in self.estado_bloqueante],
            "counts": self.count_by_categoria(),
            "disclaimer": DISCLAIMER_DA,
        }


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _safe_load_json(path: "str | Path") -> "dict | None":
    try:
        p = Path(path)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _step_ok(step_id: str, message: str = "", outputs: "list[str] | None" = None,
             warnings: "list[str] | None" = None) -> DAFlowStep:
    status = "WARNING" if warnings else "OK"
    return DAFlowStep(
        step_id=step_id,
        name=_STEP_NAMES.get(step_id, step_id),
        status=status,
        message=message,
        output_files=outputs or [],
        warnings=warnings or [],
    )


def _step_failed(step_id: str, error: str) -> DAFlowStep:
    return DAFlowStep(
        step_id=step_id,
        name=_STEP_NAMES.get(step_id, step_id),
        status="FAILED",
        message=error,
        errors=[error],
    )


def _step_skipped(step_id: str, reason: str = "") -> DAFlowStep:
    return DAFlowStep(
        step_id=step_id,
        name=_STEP_NAMES.get(step_id, step_id),
        status="SKIPPED",
        message=reason or "Omitido por fallo en paso anterior requerido.",
    )


# ---------------------------------------------------------------------------
# Pasos del flujo
# ---------------------------------------------------------------------------

def _run_technical_pipeline(exp_path: Path, write: bool, mode: str) -> DAFlowStep:
    step_id = "TECHNICAL_PIPELINE"
    try:
        from eia_agent.core.technical_pipeline import (
            run_technical_pipeline,
            write_pipeline_outputs,
        )
        result = run_technical_pipeline(exp_path, write_outputs=write, mode=mode)
        warnings = [s.step_id for s in result.steps if s.status == "WARNING"]
        failed = [s.step_id for s in result.steps if s.status in ("FAILED", "BLOCKED")]
        ok_count = sum(1 for s in result.steps if s.status not in ("FAILED", "BLOCKED", "SKIPPED"))
        total = len(result.steps)
        message = f"{ok_count}/{total} pasos OK"
        if failed:
            message += f" | Fallidos: {', '.join(failed)}"
        outputs: list[str] = []
        if write:
            aud_dir = exp_path / "auditoria"
            jp, mp = write_pipeline_outputs(result, aud_dir)
            outputs = [str(jp), str(mp)]
        status = "FAILED" if failed else ("WARNING" if warnings else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=warnings,
            errors=failed,
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_manifest(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_MANIFEST"
    try:
        from eia_agent.core.document_manifest import (
            build_document_manifest,
            write_document_manifest_outputs,
        )
        result = build_document_manifest(exp_path)
        ready = result.ready_count()
        partial = result.partial_count()
        missing = result.missing_count()
        total = len(getattr(result, "manifest_items", []))
        message = f"{ready} READY / {partial} PARTIAL / {missing} MISSING de {total}"
        outputs: list[str] = []
        if write:
            doc_dir = exp_path / "documento"
            jp, mp = write_document_manifest_outputs(result, doc_dir)
            outputs = [str(jp), str(mp)]
        status = "FAILED" if missing > 0 else ("WARNING" if partial > 0 else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_build_md(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_BUILD_MD"
    try:
        from eia_agent.core.document_markdown_builder import build_document_markdown
        result = build_document_markdown(exp_path, write_outputs=write)
        generated = result.generated_count()
        partial = result.partial_count()
        missing = result.missing_count()
        message = f"{generated} GENERATED / {partial} PARTIAL / {missing} MISSING"
        outputs: list[str] = []
        if write:
            md_p = exp_path / "documento" / "documento_ambiental_borrador.md"
            if md_p.exists():
                outputs = [str(md_p)]
        partial_blocks = [b.block_id for b in result.blocks if b.status == "PARTIAL"]
        status = "FAILED" if missing > 0 else ("WARNING" if partial_blocks else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=[f"Bloque {b} PARTIAL" for b in partial_blocks],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_build_docx(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_BUILD_DOCX"
    try:
        from eia_agent.core.document_docx_builder import build_docx_from_expediente
        result = build_docx_from_expediente(exp_path, write_outputs=write)
        message = (
            f"{result.heading_count} headings, {result.paragraph_count} parrafos"
            if result.generated else "no generado (dry-run o MD faltante)"
        )
        outputs: list[str] = []
        if write and result.generated:
            docx_p = exp_path / "documento" / "documento_ambiental_borrador.docx"
            if docx_p.exists():
                outputs = [str(docx_p)]
        warnings = list(result.warnings) if result.warnings else []
        status = "WARNING" if warnings else "OK"
        if not result.generated and write:
            status = "FAILED"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=warnings,
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_figures(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_FIGURES"
    try:
        from eia_agent.core.document_figure_inserter import insert_figures_into_document
        result = insert_figures_into_document(exp_path, write_outputs=write)
        found = result.found_count()
        inserted = result.inserted_count()
        omitted = result.skipped_count()
        message = f"{found} encontradas, {inserted} insertadas, {omitted} omitidas"
        outputs: list[str] = []
        if write and result.generated:
            docx_p = exp_path / "documento" / "documento_ambiental_borrador_con_figuras.docx"
            if docx_p.exists():
                outputs = [str(docx_p)]
        status = "WARNING" if omitted > 0 else "OK"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=[f"{omitted} figura(s) omitidas"] if omitted > 0 else [],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_qc(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_QC"
    try:
        from eia_agent.core.document_quality_checker import (
            run_document_quality_check,
            write_document_quality_outputs,
        )
        result = run_document_quality_check(exp_path)
        message = result.summary().split("\n")[0] if result.summary() else result.status
        outputs: list[str] = []
        if write:
            doc_dir = exp_path / "documento"
            jp, mp = write_document_quality_outputs(result, doc_dir)
            outputs = [str(jp), str(mp)]
        errors = [i.message for i in result.issues if i.severity == "ERROR"]
        warnings = [i.message for i in result.issues if i.severity == "WARNING"]
        status = "FAILED" if errors else ("WARNING" if warnings else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=warnings[:5],
            errors=errors[:5],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_package(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_PACKAGE"
    try:
        from eia_agent.core.document_package_builder import (
            build_document_package,
            write_package_build_outputs,
        )
        result = build_document_package(exp_path, write_outputs=write, overwrite=True)
        missing_req = result.missing_required_count()
        message = f"Requeridos faltantes: {missing_req}"
        outputs: list[str] = []
        if write:
            doc_dir = exp_path / "documento"
            jp, mp = write_package_build_outputs(result, doc_dir)
            outputs = [str(result.package_dir), str(jp)]
        status = "FAILED" if missing_req > 0 else "OK"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_export(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_EXPORT"
    try:
        from eia_agent.core.document_exporter import (
            export_document_package,
            write_export_result_outputs,
        )
        result = export_document_package(
            exp_path, write_outputs=write, generate_pdf=False, overwrite=True
        )
        zip_ok = result.zip_path is not None and Path(result.zip_path).exists() if write else True
        message = f"ZIP: {'OK' if zip_ok else 'NO GENERADO'} | errores: {result.error_count()}"
        outputs: list[str] = []
        if write and result.zip_path:
            outputs = [str(result.zip_path)]
        status = "FAILED" if result.error_count() > 0 else "OK"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=[w.message for w in result.warnings] if hasattr(result, "warnings") else [],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_presentation(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_PRESENTATION"
    try:
        from eia_agent.core.document_presentation_preparer import (
            prepare_document_for_presentation,
        )
        result = prepare_document_for_presentation(
            exp_path, write_outputs=write, create_final_docx=True
        )
        checklist_items = getattr(result, "checklist_items", [])
        ok_items = sum(1 for i in checklist_items if i.status == "OK")
        total_items = len(checklist_items)
        message = f"Checklist: {ok_items}/{total_items} OK"
        outputs: list[str] = []
        if write:
            outputs = [str(f) for f in result.generated_files]
        warnings = [i.recommendation or i.description for i in checklist_items if i.status == "WARNING"]
        errors = [i.recommendation or i.description for i in checklist_items if i.status == "ERROR"]
        status = "FAILED" if errors else ("WARNING" if warnings else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=warnings[:3],
            errors=errors[:3],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_structure(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_STRUCTURE"
    try:
        from eia_agent.core.document_structure_manager import (
            find_best_available_docx,
            normalize_document_structure,
            write_document_structure_outputs,
        )
        docx_path = find_best_available_docx(exp_path)
        if docx_path is None:
            return _step_failed(step_id, "No se encontro DOCX disponible en documento/")
        out_docx = exp_path / "documento" / "documento_ambiental_estructurado.docx"
        result = normalize_document_structure(docx_path, out_docx)
        outputs: list[str] = []
        if write:
            doc_dir = exp_path / "documento"
            paths = write_document_structure_outputs(result, doc_dir)
            outputs = [str(p) for p in paths]
            if out_docx.exists():
                outputs.append(str(out_docx))
        errors = [e.get("message", "") for e in result.errors]
        warnings = [w.get("message", "") for w in result.warnings] if hasattr(result, "warnings") else []
        found_ids = {s.section_id for s in result.sections_found if s.found}
        blocks_detected = sum(1 for b in "ABCDEFGHIJK" if b in found_ids)
        message = f"Bloques A-K: {blocks_detected}/11 | valido: {result.is_valid()}"
        status = "FAILED" if errors else ("WARNING" if warnings else "OK")
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            warnings=warnings[:3],
            errors=errors[:3],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_numbering(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_NUMBERING"
    try:
        from eia_agent.core.document_numbering_manager import process_document_numbering
        result = process_document_numbering(exp_path, write_outputs=write, apply_styles=True)
        candidates = result.list_candidate_count if hasattr(result, "list_candidate_count") else 0
        applied = result.applied_count if hasattr(result, "applied_count") else 0
        message = f"Candidatos: {candidates} | Aplicados: {applied}"
        outputs: list[str] = []
        if write:
            docx_p = exp_path / "documento" / "documento_ambiental_numerado.docx"
            if docx_p.exists():
                outputs = [str(docx_p)]
        errors = [i.message for i in result.issues if i.severity == "ERROR"] if hasattr(result, "issues") else []
        status = "FAILED" if errors else "OK"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            errors=errors[:3],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


def _run_document_toc(exp_path: Path, write: bool) -> DAFlowStep:
    step_id = "DOCUMENT_TOC"
    try:
        from eia_agent.core.document_toc_manager import process_document_toc
        result = process_document_toc(
            exp_path, write_outputs=write, apply_toc=True, replace_placeholder=True
        )
        message = result.summary().split("\n")[0] if result.summary() else "TOC procesado"
        outputs: list[str] = []
        if write:
            docx_p = exp_path / "documento" / "documento_ambiental_con_toc.docx"
            if docx_p.exists():
                outputs = [str(docx_p)]
        errors = [i.message for i in result.issues if i.severity == "ERROR"] if hasattr(result, "issues") else []
        status = "FAILED" if errors else "OK"
        return DAFlowStep(
            step_id=step_id,
            name=_STEP_NAMES[step_id],
            status=status,
            message=message,
            output_files=outputs,
            errors=errors[:3],
        )
    except Exception as exc:
        return _step_failed(step_id, f"{exc}")


# ---------------------------------------------------------------------------
# Agregacion de estado
# ---------------------------------------------------------------------------

def _aggregate_estado(
    exp_path: Path,
    steps: list[DAFlowStep],
    pipeline_step: Optional[DAFlowStep],
    manifest_step: Optional[DAFlowStep],
    qc_step: Optional[DAFlowStep],
) -> tuple[list[DAEstadoItem], list[DAEstadoItem], list[DAEstadoItem]]:
    """Clasifica todos los items en CERRADO / PENDIENTE / BLOQUEANTE."""
    cerrado: list[DAEstadoItem] = []
    pendiente: list[DAEstadoItem] = []
    bloqueante: list[DAEstadoItem] = []

    # 1. Pasos del flujo documental
    for s in steps:
        if s.step_id == "TECHNICAL_PIPELINE":
            continue  # procesado por separado abajo
        if s.status == "OK":
            cerrado.append(DAEstadoItem("CERRADO", s.name, s.step_id, "OK"))
        elif s.status == "WARNING":
            for w in (s.warnings or []):
                pendiente.append(DAEstadoItem("PENDIENTE", s.name, s.step_id, "WARNING", w))
            if not s.warnings:
                pendiente.append(DAEstadoItem("PENDIENTE", s.name, s.step_id, "WARNING"))
        elif s.status in ("FAILED", "SKIPPED"):
            msg = s.errors[0] if s.errors else s.message
            bloqueante.append(DAEstadoItem("BLOQUEANTE", s.name, s.step_id, s.status, msg))

    # 2. Pipeline tecnico: pasos individuales
    pipeline_json = _safe_load_json(exp_path / "auditoria" / "technical_pipeline_result.json")
    if pipeline_json:
        for ps in pipeline_json.get("steps", []):
            sid = ps.get("step_id", "")
            sname = ps.get("name", sid)
            sstatus = ps.get("status", "")
            if sstatus == "SUCCESS":
                cerrado.append(DAEstadoItem("CERRADO", sname, "pipeline", "SUCCESS"))
            elif sstatus == "WARNING":
                pendiente.append(DAEstadoItem("PENDIENTE", sname, "pipeline", "WARNING",
                                              "Revisar advertencias del paso"))
            elif sstatus in ("FAILED", "BLOCKED"):
                errs = ps.get("errors", [])
                accion = errs[0] if errs else "Corregir el error del paso"
                bloqueante.append(DAEstadoItem("BLOQUEANTE", sname, "pipeline", sstatus, accion))
    elif pipeline_step and pipeline_step.is_failed():
        bloqueante.append(DAEstadoItem(
            "BLOQUEANTE", "Pipeline tecnico", "TECHNICAL_PIPELINE",
            "FAILED", "El pipeline tecnico no pudo ejecutarse"
        ))

    # 3. Bloques A-K desde manifest
    manifest_json = _safe_load_json(exp_path / "documento" / "document_manifest.json")
    if manifest_json:
        for block in manifest_json.get("blocks", []):
            bid = block.get("block_id", "?")
            bstatus = block.get("status", "")
            bname = f"Bloque {bid}"
            if bstatus == "READY":
                cerrado.append(DAEstadoItem("CERRADO", bname, "document_manifest", "READY"))
            elif bstatus == "PARTIAL":
                missing = block.get("missing_files", [])
                accion = f"Fuentes faltantes: {', '.join(missing[:3])}" if missing else "Revisar fuentes del bloque"
                pendiente.append(DAEstadoItem("PENDIENTE", bname, "document_manifest", "PARTIAL", accion))
            elif bstatus == "MISSING":
                bloqueante.append(DAEstadoItem("BLOQUEANTE", bname, "document_manifest", "MISSING",
                                               "Falta el input requerido para generar el bloque"))

    # 4. Auditoria final
    audit_json = _safe_load_json(exp_path / "auditoria" / "final_audit_result.json")
    if audit_json:
        blocking = audit_json.get("blocking_count", 0)
        high = audit_json.get("high_count", 0)
        status_audit = audit_json.get("status", "")
        if blocking == 0 and high == 0:
            cerrado.append(DAEstadoItem("CERRADO", "Auditoria final (AU-04)", "final_audit_result",
                                        f"CONFORME | blocking=0 high=0"))
        elif blocking > 0:
            issues = audit_json.get("issues", [])
            for iss in issues[:5]:
                if iss.get("severity") in ("BLOQUEANTE", "ALTA"):
                    bloqueante.append(DAEstadoItem(
                        "BLOQUEANTE",
                        f"Auditoria: {iss.get('code', '?')}",
                        "final_audit_result",
                        iss.get("severity", "ALTA"),
                        iss.get("message", "")[:120],
                    ))
        elif high > 0:
            pendiente.append(DAEstadoItem("PENDIENTE", "Auditoria final (AU-04)",
                                          "final_audit_result",
                                          f"{high} issue(s) ALTA",
                                          "Revisar incidencias de severidad ALTA"))

    # 5. QC documental
    qc_json = _safe_load_json(exp_path / "documento" / "document_quality_result.json")
    if qc_json:
        qc_status = qc_json.get("status", "")
        if qc_status in ("VALIDO", "VALIDO_CON_OBSERVACIONES", "OK"):
            cerrado.append(DAEstadoItem("CERRADO", "QC documental", "document_quality_result", qc_status))
        elif qc_status == "NO_CONFORME":
            errors_qc = [i.get("message", "") for i in qc_json.get("issues", [])
                         if i.get("severity") == "ERROR"]
            accion = errors_qc[0] if errors_qc else "Corregir errores de QC"
            bloqueante.append(DAEstadoItem("BLOQUEANTE", "QC documental NO_CONFORME",
                                           "document_quality_result", "NO_CONFORME", accion))
        else:
            pendiente.append(DAEstadoItem("PENDIENTE", "QC documental",
                                          "document_quality_result", qc_status))

    # 6. Checklist de presentacion
    checklist_json = _safe_load_json(exp_path / "documento" / "checklist_presentacion.json")
    if checklist_json:
        items_ok = [i for i in checklist_json.get("items", []) if i.get("status") == "OK"]
        items_err = [i for i in checklist_json.get("items", []) if i.get("status") == "ERROR"]
        items_warn = [i for i in checklist_json.get("items", []) if i.get("status") == "WARNING"]
        for it in items_err[:3]:
            bloqueante.append(DAEstadoItem("BLOQUEANTE", f"Checklist: {it.get('check_id', '?')}",
                                           "checklist_presentacion", "ERROR",
                                           it.get("message", "")))
        for it in items_warn[:3]:
            pendiente.append(DAEstadoItem("PENDIENTE", f"Checklist: {it.get('check_id', '?')}",
                                          "checklist_presentacion", "WARNING",
                                          it.get("message", "")))
        if items_ok and not items_err:
            cerrado.append(DAEstadoItem("CERRADO", f"Checklist presentacion ({len(items_ok)} OK)",
                                        "checklist_presentacion", "OK"))

    return cerrado, pendiente, bloqueante


def _determine_resultado_flujo(
    estado_cerrado: list[DAEstadoItem],
    estado_pendiente: list[DAEstadoItem],
    estado_bloqueante: list[DAEstadoItem],
    steps: list[DAFlowStep],
) -> str:
    failed_steps = [s for s in steps if s.is_failed()]
    if estado_bloqueante or failed_steps:
        return "BLOQUEADO"
    if estado_pendiente:
        return "CERRADO_CON_PENDIENTES"
    return "FLUJO_COMPLETO"


# ---------------------------------------------------------------------------
# Funcion principal
# ---------------------------------------------------------------------------

def run_da_flow(
    exp_path: Path,
    write: bool = True,
    mode: str = "TEST",
) -> DAFlowResult:
    """
    Ejecuta el flujo completo DA-01 para un expediente cliente.

    Pasos:
      1. Pipeline tecnico (19 pasos)
      2. document-manifest
      3. document-build-md
      4. document-build-docx
      5. document-insert-figures
      6. document-qc
      7. document-package
      8. document-export (sin PDF)
      9. document-prepare-presentation
     10. document-structure
     11. document-numbering
     12. document-toc
     13. Estado final

    Continua aunque algún paso falle (continue-on-error=True).
    administrative_ready=False siempre.
    """
    exp_id = exp_path.name
    steps: list[DAFlowStep] = []

    # Paso 1: Pipeline tecnico
    step_pipe = _run_technical_pipeline(exp_path, write, mode)
    steps.append(step_pipe)

    # Paso 2: Manifest
    step_manifest = _run_document_manifest(exp_path, write)
    steps.append(step_manifest)

    # Paso 3: Markdown
    step_md = _run_document_build_md(exp_path, write)
    steps.append(step_md)

    # Paso 4: DOCX
    step_docx = _run_document_build_docx(exp_path, write)
    steps.append(step_docx)

    # Paso 5: Figuras
    step_figs = _run_document_figures(exp_path, write)
    steps.append(step_figs)

    # Paso 6: QC
    step_qc = _run_document_qc(exp_path, write)
    steps.append(step_qc)

    # Paso 7: Package
    step_pkg = _run_document_package(exp_path, write)
    steps.append(step_pkg)

    # Paso 8: Export ZIP
    step_exp = _run_document_export(exp_path, write)
    steps.append(step_exp)

    # Paso 9: Presentacion
    step_pres = _run_document_presentation(exp_path, write)
    steps.append(step_pres)

    # Paso 10: Structure
    step_struct = _run_document_structure(exp_path, write)
    steps.append(step_struct)

    # Paso 11: Numbering
    step_num = _run_document_numbering(exp_path, write)
    steps.append(step_num)

    # Paso 12: TOC
    step_toc = _run_document_toc(exp_path, write)
    steps.append(step_toc)

    # Paso 13: Agregar estado
    cerrado, pendiente, bloqueante = _aggregate_estado(
        exp_path, steps, step_pipe, step_manifest, step_qc
    )
    resultado_flujo = _determine_resultado_flujo(cerrado, pendiente, bloqueante, steps)

    flow_result = DAFlowResult(
        expediente_id=exp_id,
        administrative_ready=False,
        resultado_flujo=resultado_flujo,
        steps=steps,
        estado_cerrado=cerrado,
        estado_pendiente=pendiente,
        estado_bloqueante=bloqueante,
    )

    if write:
        write_da_flow_outputs(flow_result, exp_path)

    return flow_result


# ---------------------------------------------------------------------------
# Markdown del informe de estado
# ---------------------------------------------------------------------------

def build_da_flow_estado_markdown(result: DAFlowResult) -> str:
    """Genera el informe de estado del expediente en Markdown."""
    label = _RESULTADO_FLUJO_LABELS.get(result.resultado_flujo, result.resultado_flujo)
    counts = result.count_by_categoria()
    lines: list[str] = []

    lines.append(f"# Estado del Expediente — {result.expediente_id}")
    lines.append("")
    lines.append(f"> **AVISO**: {DISCLAIMER_DA}")
    lines.append("")
    lines.append(f"**Resultado**: {label}")
    lines.append(f"**Pasos ejecutados**: {result.steps_ok()}/{len(result.steps)} OK")
    lines.append(f"**Items cerrados**: {counts['CERRADO']}")
    lines.append(f"**Items pendientes**: {counts['PENDIENTE']}")
    lines.append(f"**Items bloqueantes**: {counts['BLOQUEANTE']}")
    lines.append("")

    # Pasos del flujo
    lines.append("---")
    lines.append("")
    lines.append("## Pasos ejecutados")
    lines.append("")
    lines.append("| Paso | Estado | Mensaje |")
    lines.append("|------|--------|---------|")
    for s in result.steps:
        icon = {"OK": "[OK]", "WARNING": "[AVISO]", "FAILED": "[FALLO]", "SKIPPED": "[OMITIDO]"}.get(s.status, s.status)
        msg = s.message[:80] if s.message else ""
        lines.append(f"| {s.name} | {icon} | {msg} |")
    lines.append("")

    # Cerrado
    lines.append("---")
    lines.append("")
    lines.append(f"## CERRADO ({counts['CERRADO']} items)")
    lines.append("")
    if result.estado_cerrado:
        lines.append("| Item | Fuente | Valor |")
        lines.append("|------|--------|-------|")
        for it in result.estado_cerrado:
            lines.append(f"| {it.item} | {it.fuente} | {it.valor} |")
    else:
        lines.append("_No hay items cerrados._")
    lines.append("")

    # Pendiente
    lines.append("---")
    lines.append("")
    lines.append(f"## PENDIENTE ({counts['PENDIENTE']} items)")
    lines.append("")
    if result.estado_pendiente:
        lines.append("| Item | Fuente | Valor | Accion requerida |")
        lines.append("|------|--------|-------|-----------------|")
        for it in result.estado_pendiente:
            lines.append(f"| {it.item} | {it.fuente} | {it.valor} | {it.accion} |")
    else:
        lines.append("_No hay items pendientes._")
    lines.append("")

    # Bloqueante
    lines.append("---")
    lines.append("")
    lines.append(f"## BLOQUEANTE ({counts['BLOQUEANTE']} items)")
    lines.append("")
    if result.estado_bloqueante:
        lines.append("| Item | Fuente | Valor | Accion requerida |")
        lines.append("|------|--------|-------|-----------------|")
        for it in result.estado_bloqueante:
            lines.append(f"| {it.item} | {it.fuente} | {it.valor} | {it.accion} |")
    else:
        lines.append("_No hay items bloqueantes._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Generado por EIA-Agent v2.1 — DA-01 Flujo Documento Ambiental*  ")
    lines.append(f"*{DISCLAIMER_DA}*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_da_flow_outputs(result: DAFlowResult, exp_path: Path) -> tuple[Path, Path]:
    """Escribe estado_expediente_da.json y .md en documento/."""
    doc_dir = exp_path / "documento"
    doc_dir.mkdir(parents=True, exist_ok=True)

    json_path = doc_dir / "estado_expediente_da.json"
    md_path = doc_dir / "estado_expediente_da.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    md_content = build_da_flow_estado_markdown(result)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return json_path, md_path
