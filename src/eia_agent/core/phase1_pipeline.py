"""
phase1_pipeline -- IN-06
Pipeline programático de Fase 1: indexa documentos de entrada, procesa DOCX,
extrae entidades y clasifica evidencias. Consolida los hechos candidatos en
memoria y detecta conflictos básicos.

No usa IA. No procesa PDFs. No escribe automáticamente (requiere write_outputs=True).
No modifica inputs. No crea hechos_confirmados.json real.

Uso:
    from eia_agent.core.phase1_pipeline import run_phase1

    result = run_phase1("expediente-EIA-2026-RECIMETAL-PARCELA")
    print(result.summary())

    # Con escritura explícita:
    result = run_phase1("expediente-EIA-2026-RECIMETAL-PARCELA", write_outputs=True)
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from eia_agent.core.input_indexer import build_inputs_index
from eia_agent.core.evidence_classifier import (
    ClassificationResult,
    classify_entities_from_docx,
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _fact_to_dict(fact) -> dict:
    """Convierte un CandidateFact a dict JSON-serializable."""
    return {
        "id": fact.id,
        "categoria": fact.categoria,
        "campo": fact.campo,
        "valor": str(fact.valor) if fact.valor is not None else None,
        "estado": fact.estado,
        "fuentes": list(fact.fuentes),
        "entity_type": fact.entity_type,
        "confidence": fact.confidence,
        "context": fact.context,
        "normalized_value": fact.normalized_value,
        "notes": list(fact.notes),
    }


# ---------------------------------------------------------------------------
# Dataclass de resultado
# ---------------------------------------------------------------------------

@dataclass
class Phase1Result:
    """Resultado completo del pipeline de Fase 1.

    Contiene el índice de documentos, los hechos candidatos consolidados,
    estadísticas básicas, avisos y notas.
    No confirma nada. No escribe nada automáticamente.
    """
    expediente_id: str
    inputs_index: dict
    candidate_facts: list[dict]
    documents_processed: int
    docx_processed: int
    pdf_pending: int
    warnings: list[str]
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Fase 1 — {self.expediente_id}",
            f"  Documentos encontrados : {self.documents_processed}",
            f"  DOCX procesados        : {self.docx_processed}",
            f"  PDFs pendientes        : {self.pdf_pending}",
            f"  Hechos candidatos      : {len(self.candidate_facts)}",
        ]
        if self.warnings:
            lines.append(f"  Avisos                 : {len(self.warnings)}")
            for w in self.warnings[:5]:
                lines.append(f"    - {w}")
            if len(self.warnings) > 5:
                lines.append(f"    ... y {len(self.warnings) - 5} aviso(s) más")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "inputs_index": self.inputs_index,
            "candidate_facts": self.candidate_facts,
            "documents_processed": self.documents_processed,
            "docx_processed": self.docx_processed,
            "pdf_pending": self.pdf_pending,
            "warnings": self.warnings,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------

def merge_candidate_facts(results: list[ClassificationResult]) -> list[dict]:
    """Concatena hechos candidatos de múltiples ClassificationResult.

    No deduplica. No resuelve conflictos. No eleva estados.
    Conserva fuentes de cada hecho.
    """
    merged: list[dict] = []
    for cr in results:
        for fact in cr.facts:
            merged.append(_fact_to_dict(fact))
    return merged


def detect_phase1_basic_conflicts(candidate_facts: list[dict]) -> list[dict]:
    """Detecta conflictos básicos entre hechos candidatos.

    Campos revisados:
    - referencia_catastral
    - nombre_promotor, titular
    - capacidad
    - superficie_parcela, superficie_catastral, superficie_construida,
      superficie_util, superficie_nave, superficie_no_clasificada

    Solo registra conflictos. No los resuelve ni eleva estados.
    """
    _CONFLICT_FIELDS = frozenset({
        "referencia_catastral",
        "nombre_promotor",
        "titular",
        "capacidad",
        "superficie_parcela",
        "superficie_catastral",
        "superficie_construida",
        "superficie_util",
        "superficie_nave",
        "superficie_no_clasificada",
    })

    by_campo: dict[str, list[dict]] = defaultdict(list)
    for fact in candidate_facts:
        campo = fact.get("campo", "")
        if campo in _CONFLICT_FIELDS:
            by_campo[campo].append(fact)

    conflicts: list[dict] = []
    for campo, facts in by_campo.items():
        # Valores normalizados (sin espacios, mayúsculas) para comparación
        valores_norm = {
            str(f.get("valor", "")).strip().upper()
            for f in facts
            if f.get("valor") is not None
        }
        if len(valores_norm) <= 1:
            continue

        fuentes = sorted({
            s for f in facts for s in f.get("fuentes", [])
        })
        conflicts.append({
            "tipo": "valor_multiple",
            "campo": campo,
            "valores": list(valores_norm),
            "fuentes": fuentes,
            "n_hechos": len(facts),
        })

    return conflicts


# ---------------------------------------------------------------------------
# Escritura opcional
# ---------------------------------------------------------------------------

def _build_phase1_markdown(result: Phase1Result) -> str:
    """Genera un resumen markdown corto de la Fase 1."""
    lines = [
        f"# Fase 1 — Resultado de ingesta",
        f"",
        f"**Expediente**: {result.expediente_id}",
        f"",
        f"## Estadísticas",
        f"",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Documentos encontrados | {result.documents_processed} |",
        f"| DOCX procesados | {result.docx_processed} |",
        f"| PDFs pendientes | {result.pdf_pending} |",
        f"| Hechos candidatos | {len(result.candidate_facts)} |",
        f"",
    ]
    if result.warnings:
        lines += ["## Avisos", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
    if result.notes:
        lines += ["## Notas", ""]
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)


def _write_phase1_outputs(result: Phase1Result, output_dir: Path) -> tuple[Path, Path]:
    """Escribe phase1_result.json y phase1_result.md en output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "phase1_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    md_path = output_dir / "phase1_result.md"
    md_path.write_text(_build_phase1_markdown(result), encoding="utf-8")

    return json_path, md_path


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def run_phase1(
    expediente_path: "str | Path",
    write_outputs: bool = False,
    output_dir: str = "control_interno",
) -> Phase1Result:
    """Ejecuta el pipeline de Fase 1 sobre un expediente.

    Args:
        expediente_path: Ruta al directorio del expediente.
        write_outputs:   Si True, escribe phase1_result.json y
                         phase1_result.md en output_dir. Por defecto False.
        output_dir:      Subdirectorio relativo al expediente donde escribir
                         (por defecto "control_interno").

    Returns:
        Phase1Result con hechos candidatos, estadísticas y avisos.
        No modifica inputs. No crea hechos_confirmados.json real.
    """
    exp_path = Path(expediente_path)
    expediente_id = exp_path.name
    warnings: list[str] = []
    notes: list[str] = []

    # 1. Construir índice de documentos (parse_docx=False para no duplicar parseo)
    index = build_inputs_index(exp_path, parse_docx=False)
    warnings.extend(index.warnings)

    # 2. Expediente sin documentos
    if index.document_count() == 0:
        warnings.append("No se encontraron documentos en la carpeta de entradas.")
        result = Phase1Result(
            expediente_id=expediente_id,
            inputs_index=index.to_dict(),
            candidate_facts=[],
            documents_processed=0,
            docx_processed=0,
            pdf_pending=0,
            warnings=warnings,
            notes=notes,
        )
        if write_outputs:
            _write_phase1_outputs(result, exp_path / output_dir)
        return result

    # 3. Contar PDFs pendientes
    pdf_pending = sum(
        1 for d in index.documents if d.status == "PENDIENTE_PARSER_PDF"
    )
    if pdf_pending > 0:
        warnings.append(
            f"{pdf_pending} documento(s) PDF detectado(s) sin parser disponible; "
            "no procesados en Fase 1 (IN-04 pendiente)."
        )

    # 4. Procesar cada DOCX (extension=.docx, status=PROCESADO optimista)
    classification_results: list[ClassificationResult] = []
    docx_docs = [
        d for d in index.documents
        if d.extension.lower() == ".docx" and d.status == "PROCESADO"
    ]

    for doc in docx_docs:
        doc_full_path = exp_path / doc.relative_path
        try:
            cr = classify_entities_from_docx(
                str(doc_full_path),
                source_doc_id=doc.doc_id,
            )
            classification_results.append(cr)
            if cr.warnings:
                warnings.extend(cr.warnings)
        except Exception as exc:
            warnings.append(
                f"Error al procesar '{doc.filename}' ({doc.doc_id}): {exc}"
            )

    # 5. Consolidar hechos candidatos
    candidate_facts = merge_candidate_facts(classification_results)

    # 6. Construir resultado
    result = Phase1Result(
        expediente_id=expediente_id,
        inputs_index=index.to_dict(),
        candidate_facts=candidate_facts,
        documents_processed=index.document_count(),
        docx_processed=len(docx_docs),
        pdf_pending=pdf_pending,
        warnings=warnings,
        notes=notes,
    )

    if write_outputs:
        _write_phase1_outputs(result, exp_path / output_dir)

    return result
