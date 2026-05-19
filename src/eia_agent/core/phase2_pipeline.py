"""
phase2_pipeline -- OB-06
Pipeline programático de Fase 2: toma candidate facts de Fase 1,
construye el ObjectScope, ejecuta validación de Gate 2 y produce
un resultado estructurado.

No usa IA. No resuelve contradicciones. No crea AT automáticas.
No cierra gaps. No marca aptitud administrativa.
No escribe automáticamente (requiere write_outputs=True).
No modifica inputs.

Uso:
    from eia_agent.core.phase2_pipeline import run_phase2

    result = run_phase2("expediente-EIA-2026-RECIMETAL-PARCELA")
    print(result.summary())

    # Con escritura explícita:
    result = run_phase2(
        "expediente-EIA-2026-RECIMETAL-PARCELA",
        write_outputs=True,
        overrides={"modo": "GABINETE"},
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.evidence_classifier import CandidateFact, ClassificationResult
from eia_agent.core.object_scope_builder import ObjectScope, build_object_scope
from eia_agent.core.object_gate_validator import evaluate_gate_2


# ---------------------------------------------------------------------------
# Dataclass de resultado
# ---------------------------------------------------------------------------

@dataclass
class Phase2Result:
    """Resultado completo del pipeline de Fase 2.

    Contiene el ObjectScope construido, el resultado del Gate 2,
    estadísticas e incidencias. No confirma aptitud administrativa.
    """
    expediente_id: str
    object_scope: dict
    gate2_passed: bool
    gate2_summary: str
    issues: list[dict]
    warnings: list[str]
    notes: list[str] = field(default_factory=list)

    def summary(self) -> str:
        estado = "APTO" if self.gate2_passed else "BLOQUEADO"
        lines = [
            f"Fase 2 — {self.expediente_id}",
            f"  Gate 2                 : {estado}",
            f"  Errores Gate 2         : {sum(1 for i in self.issues if i.get('severity') == 'ERROR')}",
            f"  Avisos Gate 2          : {sum(1 for i in self.issues if i.get('severity') == 'WARNING')}",
        ]
        scope = self.object_scope
        lines.append(f"  Titular                : {scope.get('titular') or 'NO DECLARADO'}")
        lines.append(f"  Referencia catastral   : {scope.get('referencia_catastral') or 'NO DECLARADO'}")
        lines.append(f"  Modo                   : {scope.get('modo', 'NO_DECLARADO')}")
        if self.warnings:
            lines.append(f"  Avisos pipeline        : {len(self.warnings)}")
            for w in self.warnings[:3]:
                lines.append(f"    - {w}")
            if len(self.warnings) > 3:
                lines.append(f"    ... y {len(self.warnings) - 3} aviso(s) más")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "object_scope": self.object_scope,
            "gate2_passed": self.gate2_passed,
            "gate2_summary": self.gate2_summary,
            "issues": self.issues,
            "warnings": self.warnings,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Función auxiliar: reconstruir ClassificationResult desde phase1 JSON
# ---------------------------------------------------------------------------

def build_classification_result_from_phase1(
    phase1_data: dict,
) -> ClassificationResult:
    """Reconstruye un ClassificationResult mínimo desde candidate_facts de Fase 1.

    No re-extrae desde DOCX. Los hechos candidatos ya clasificados por IN-03
    se deserializan directamente en objetos CandidateFact.

    Args:
        phase1_data: Dict cargado de phase1_result.json.

    Returns:
        ClassificationResult con los facts del phase1_data.
        Lista vacía si no hay candidate_facts.
    """
    facts: list[CandidateFact] = []
    for d in phase1_data.get("candidate_facts", []):
        fact = CandidateFact(
            id=d.get("id"),
            categoria=d.get("categoria", ""),
            campo=d.get("campo", ""),
            valor=d.get("valor"),
            estado=d.get("estado", "DECLARADO"),
            fuentes=list(d.get("fuentes", [])),
            entity_type=d.get("entity_type", ""),
            confidence=d.get("confidence", "MEDIUM"),
            context=d.get("context"),
            normalized_value=d.get("normalized_value"),
            notes=list(d.get("notes", [])),
        )
        facts.append(fact)
    return ClassificationResult(facts=facts)


# ---------------------------------------------------------------------------
# Escritura opcional
# ---------------------------------------------------------------------------

def _build_phase2_markdown(result: Phase2Result) -> str:
    """Genera un resumen markdown corto de la Fase 2."""
    estado = "APTO ✅" if result.gate2_passed else "BLOQUEADO 🔴"
    scope = result.object_scope
    lines = [
        "# Fase 2 — Resultado del cierre del objeto evaluado",
        "",
        f"**Expediente**: {result.expediente_id}",
        "",
        "## Gate 2",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Estado | {estado} |",
        f"| Errores | {sum(1 for i in result.issues if i.get('severity') == 'ERROR')} |",
        f"| Avisos | {sum(1 for i in result.issues if i.get('severity') == 'WARNING')} |",
        f"| Info | {sum(1 for i in result.issues if i.get('severity') == 'INFO')} |",
        "",
        "## Objeto evaluado",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Titular | {scope.get('titular') or 'NO DECLARADO'} |",
        f"| Referencia catastral | {scope.get('referencia_catastral') or 'NO DECLARADO'} |",
        f"| Modo | {scope.get('modo', 'NO_DECLARADO')} |",
        f"| Operaciones incluidas | {len(scope.get('operaciones_incluidas', []))} |",
        f"| Operaciones excluidas | {len(scope.get('operaciones_excluidas', []))} |",
        f"| AT activos | {len(scope.get('at_activos', []))} |",
        f"| Gaps | {len(scope.get('gaps', []))} |",
        "",
    ]
    if result.issues:
        lines += ["## Incidencias Gate 2", ""]
        for issue in result.issues:
            sev = issue.get("severity", "?")
            code = issue.get("code", "")
            msg = issue.get("message", "")
            lines.append(f"- **[{sev}]** `{code}`: {msg}")
        lines.append("")
    if result.warnings:
        lines += ["## Avisos del pipeline", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")
    if result.notes:
        lines += ["## Notas", ""]
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")
    return "\n".join(lines)


def _write_phase2_outputs(
    result: Phase2Result,
    scope: ObjectScope,
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    """Escribe phase2_result.json, ficha_objeto_evaluado.md y object_scope.json."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "phase2_result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    md_path = output_dir / "ficha_objeto_evaluado.md"
    md_path.write_text(scope.to_markdown(), encoding="utf-8")

    scope_path = output_dir / "object_scope.json"
    with open(scope_path, "w", encoding="utf-8") as f:
        json.dump(scope.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    return json_path, md_path, scope_path


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def run_phase2(
    expediente_path: "str | Path",
    phase1_result_path: "str | Path | None" = None,
    write_outputs: bool = False,
    output_dir: str = "control_interno",
    overrides: Optional[dict] = None,
    test_mode: bool = True,
    context: Optional[dict] = None,
) -> Phase2Result:
    """Ejecuta el pipeline de Fase 2 sobre un expediente.

    Args:
        expediente_path:     Ruta al directorio del expediente.
        phase1_result_path:  Ruta explícita a phase1_result.json. Si None,
                             busca en control_interno/phase1_result.json.
        write_outputs:       Si True, escribe phase2_result.json,
                             ficha_objeto_evaluado.md y object_scope.json
                             en output_dir. Por defecto False.
        output_dir:          Subdirectorio relativo al expediente para escritura
                             (por defecto "control_interno").
        overrides:           Dict de campos a sobreescribir en el ObjectScope.
                             Claves admitidas: titular, referencia_catastral,
                             modo, coordenadas_wgs84, coordenadas_utm,
                             operaciones_incluidas, operaciones_excluidas,
                             at_activos, gaps, superficie_m2, capacidad.
        test_mode:           True (defecto) = modo test, más permisivo.
                             False = modo producción, criterio estricto.
        context:             Dict opcional para evaluate_gate_2():
                             rc_verificada, cont_abiertos, uso_catastral,
                             uso_declarado.

    Returns:
        Phase2Result con ObjectScope, resultado Gate 2, incidencias y avisos.
        No modifica inputs. No crea AT. No resuelve contradicciones.

    Raises:
        FileNotFoundError: si phase1_result.json no existe y no se proporciona
                           ruta explícita.
    """
    exp_path = Path(expediente_path)
    expediente_id = exp_path.name
    warnings: list[str] = []
    notes: list[str] = []

    # 1. Localizar phase1_result.json
    if phase1_result_path is not None:
        p1_path = Path(phase1_result_path)
    else:
        p1_path = exp_path / output_dir / "phase1_result.json"

    if not p1_path.exists():
        raise FileNotFoundError(
            f"phase1_result.json no encontrado en: {p1_path}\n"
            "Ejecute primero:\n"
            f"  python run_expediente.py {exp_path.name} phase1 --write\n"
            "o pase una ruta explícita via phase1_result_path."
        )

    # 2. Cargar datos de Fase 1
    try:
        with open(p1_path, encoding="utf-8") as f:
            phase1_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {p1_path}: {exc}") from exc

    if phase1_data.get("warnings"):
        warnings.extend(
            f"[Fase 1] {w}" for w in phase1_data["warnings"]
            if not any(w == existing.removeprefix("[Fase 1] ") for existing in warnings)
        )

    # 3. Reconstruir ClassificationResult desde candidate_facts
    classification = build_classification_result_from_phase1(phase1_data)
    if not classification.facts:
        notes.append(
            "phase1_result.json no contiene hechos candidatos. "
            "ObjectScope construido únicamente desde overrides."
        )

    # 4. Construir ObjectScope (OB-01)
    scope = build_object_scope(
        expediente_id,
        classification=classification,
        overrides=overrides,
    )

    # 5. Evaluar Gate 2 (OB-02)
    gate_result = evaluate_gate_2(scope, test_mode=test_mode, context=context)

    # 6. Convertir incidencias a dicts serializables
    issues_dicts = [
        {
            "severity": issue.severity,
            "code": issue.code,
            "message": issue.message,
            "field": issue.field,
            "recommendation": issue.recommendation,
        }
        for issue in gate_result.issues
    ]

    # 7. Construir resultado
    result = Phase2Result(
        expediente_id=expediente_id,
        object_scope=scope.to_dict(),
        gate2_passed=gate_result.passed,
        gate2_summary=gate_result.summary(),
        issues=issues_dicts,
        warnings=warnings,
        notes=notes,
    )

    # 8. Escritura opcional
    if write_outputs:
        _write_phase2_outputs(result, scope, exp_path / output_dir)

    return result
