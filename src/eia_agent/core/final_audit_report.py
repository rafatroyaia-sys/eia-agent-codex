"""
final_audit_report -- AU-04
Informe final de auditoría del expediente EIA.

Combina los resultados de:
  AU-01 — Checklist art.45.1 Ley 21/2013
  AU-02 — Validador de prudencia metodológica
  AU-03 — Validador de trazabilidad HC ↔ DA

Y emite:
  - Calificación final: CONFORME / CONFORME_CON_OBSERVACIONES / NO_CONFORME / INCOMPLETO
  - Lista de incidencias ordenadas por severidad: BLOQUEANTE / ALTA / MEDIA / BAJA / INFO
  - Informe en JSON y Markdown

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No ejecuta AU-01/AU-02/AU-03 automáticamente; solo combina resultados existentes.
  - No corrige automáticamente textos ni expedientes.
  - No modifica los archivos de auditoría previos.
  - administrative_ready siempre False.
  - La calificación es interna: no equivale a aptitud administrativa.
  - La clasificación del expediente corresponde al órgano ambiental.

Dependencias: ninguna de otros módulos propios (stand-alone).
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

FINAL_AUDIT_STATUS: list[str] = [
    "CONFORME",
    "CONFORME_CON_OBSERVACIONES",
    "NO_CONFORME",
    "INCOMPLETO",
]

FINAL_AUDIT_SEVERITY: list[str] = [
    "BLOQUEANTE",
    "ALTA",
    "MEDIA",
    "BAJA",
    "INFO",
]

AUDIT_SOURCE: list[str] = [
    "AU-01_ART45",
    "AU-02_PRUDENCE",
    "AU-03_TRACEABILITY",
    "RD-04_BLOCK_CONSISTENCY",
    "RD-06_CONESA_CHECK",
    "RD-07_POSITIVE_GAPS",
    "RD-08_DIAGNOSTIC_MEASURES",
    "RD-09_PRL_MEASURES",
    "IM-09_CONDITIONAL_CHAINS",
    "SISTEMA",
]

# Umbral de afirmaciones NO_TRAZADAS que activa un issue BLOQUEANTE
_UNTRACED_BLOQUEANTE_THRESHOLD: int = 5

# Frases de prudencia que indican cierre indebido grave → BLOQUEANTE
_BLOQUEANTE_PRUDENCE_PHRASES: frozenset[str] = frozenset({
    "sin afeccion",
    "cumple limites",
    "no hay red natura",
    "sin especies protegidas",
    "sin afeccion patrimonial",
    "sin afeccion significativa",
    "sin afeccion apreciable",
    "fuera de red natura",
    "no afecta a red natura",
})

# Código prefijo para incidencias de "auditoría faltante" (→ INCOMPLETO en status)
_MISSING_CODE_PREFIX: str = "AU04-M"


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# FinalAuditIssue
# ---------------------------------------------------------------------------

@dataclass
class FinalAuditIssue:
    """Incidencia consolidada del informe final de auditoría."""

    severity: str
    """BLOQUEANTE / ALTA / MEDIA / BAJA / INFO."""

    source: str
    """Fuente: AU-01_ART45 / AU-02_PRUDENCE / AU-03_TRACEABILITY / SISTEMA."""

    code: str
    """Código de la incidencia (AU04-E001, AU04-W001…)."""

    message: str
    """Descripción de la incidencia."""

    recommendation: str
    """Acción recomendada."""

    related_requirement: str | None = None
    """Requisito afectado (ART45-01…ART45-12) o None."""

    related_file: str | None = None
    """Archivo fuente original (path relativo) o None."""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "source": self.source,
            "code": self.code,
            "message": self.message,
            "recommendation": self.recommendation,
            "related_requirement": self.related_requirement,
            "related_file": self.related_file,
        }

    def summary(self) -> str:
        req = f" ({self.related_requirement})" if self.related_requirement else ""
        s = f"[{self.severity:10s}] {self.code}{req} | {self.message[:70]}"
        return _ascii_safe(s)


# ---------------------------------------------------------------------------
# FinalAuditResult
# ---------------------------------------------------------------------------

@dataclass
class FinalAuditResult:
    """Resultado consolidado del informe final de auditoría AU-04."""

    expediente_id: str
    status: str
    """CONFORME / CONFORME_CON_OBSERVACIONES / NO_CONFORME / INCOMPLETO."""

    administrative_ready: bool = False
    """Siempre False. Esta auditoría no declara aptitud administrativa."""

    art45_summary: dict = field(default_factory=dict)
    prudence_summary: dict = field(default_factory=dict)
    traceability_summary: dict = field(default_factory=dict)
    block_consistency_summary: dict = field(default_factory=dict)
    conesa_check_summary: dict = field(default_factory=dict)
    diagnostic_measure_summary: dict = field(default_factory=dict)
    prl_measure_summary: dict = field(default_factory=dict)
    conditional_chain_summary: dict = field(default_factory=dict)
    positive_gap_summary: dict = field(default_factory=dict)

    issues: list[FinalAuditIssue] = field(default_factory=list)
    blocking_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Garantía: administrative_ready nunca True
        object.__setattr__(self, "administrative_ready", False)

    def error_count(self) -> int:
        """Incidencias BLOQUEANTE + ALTA (las que implican NO_CONFORME)."""
        return self.blocking_count + self.high_count

    def has_blocking_issues(self) -> bool:
        return self.blocking_count > 0

    def is_conforme(self) -> bool:
        """True solo si status == CONFORME (sin observaciones)."""
        return self.status == "CONFORME"

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "status": self.status,
            "administrative_ready": False,
            "art45_summary": self.art45_summary,
            "prudence_summary": self.prudence_summary,
            "traceability_summary": self.traceability_summary,
            "block_consistency_summary": self.block_consistency_summary,
            "conesa_check_summary": self.conesa_check_summary,
            "diagnostic_measure_summary": self.diagnostic_measure_summary,
            "prl_measure_summary": self.prl_measure_summary,
            "conditional_chain_summary": self.conditional_chain_summary,
            "positive_gap_summary": self.positive_gap_summary,
            "issues": [i.to_dict() for i in self.issues],
            "blocking_count": self.blocking_count,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "error_count": self.error_count(),
            "has_blocking_issues": self.has_blocking_issues(),
            "is_conforme": self.is_conforme(),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"--- AU-04 Informe final de auditoria ---",
            f"Expediente         : {self.expediente_id}",
            f"Estado final       : {self.status}",
            f"Aptitud admin.     : NO DECLARADA (administrative_ready=False)",
            f"Incidencias BLOQ.  : {self.blocking_count}",
            f"Incidencias ALTA   : {self.high_count}",
            f"Incidencias MEDIA  : {self.medium_count}",
            f"Incidencias BAJA   : {self.low_count}",
        ]
        if self.error_count() > 0:
            for iss in self.issues[:3]:
                if iss.severity in ("BLOQUEANTE", "ALTA"):
                    lines.append(
                        f"  ! [{iss.severity}] {_ascii_safe(iss.message[:70])}"
                    )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# load_audit_json
# ---------------------------------------------------------------------------

def load_audit_json(path: "str | Path") -> dict | None:
    """Carga un JSON de auditoría si existe.

    Returns:
        Dict con el contenido del JSON, o None si el archivo no existe.
        Si el JSON está corrupto, devuelve un dict de error con clave 'corrupt'.
    """
    p = Path(path)
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "corrupt": True,
            "error": str(exc),
            "path": str(p),
        }


# ---------------------------------------------------------------------------
# extract_final_issues_from_art45
# ---------------------------------------------------------------------------

def extract_final_issues_from_art45(data: dict | None) -> list[FinalAuditIssue]:
    """Extrae incidencias finales del checklist art.45 (AU-01).

    Si data es None: genera issue AU04-M001 (auditoría faltante → INCOMPLETO).
    Si data corrupta: genera issue ALTA.

    Para cada ítem del checklist:
      NO_CUBIERTO → ALTA
      PARCIAL → MEDIA

    Para cada issue del checklist:
      ERROR → ALTA
      WARNING → BAJA
    """
    if data is None:
        return [FinalAuditIssue(
            severity="ALTA",
            source="SISTEMA",
            code=f"{_MISSING_CODE_PREFIX}001",
            message=(
                "Auditoria AU-01 (Checklist art.45) no disponible. "
                "Ejecute 'audit-art45 --write' antes de generar el informe final."
            ),
            recommendation="Ejecutar: python run_expediente.py <exp> audit-art45 --write",
        )]

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="AU-01_ART45",
            code="AU04-E101",
            message=f"JSON de AU-01 corrupto: {data.get('error', 'error desconocido')}",
            recommendation="Regenerar: python run_expediente.py <exp> audit-art45 --write",
        )]

    issues: list[FinalAuditIssue] = []

    # Ítems del checklist
    for item in data.get("items", []):
        req_id = item.get("requirement_id")
        title = item.get("title", req_id or "")
        status = item.get("status", "")

        if status == "NO_CUBIERTO":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="AU-01_ART45",
                code="AU04-E102",
                message=f"Requisito {req_id} ({title[:60]}) NO CUBIERTO en el expediente.",
                recommendation=(
                    "Incluir los elementos requeridos por el art. 45.1 Ley 21/2013 "
                    f"para el requisito {req_id}."
                ),
                related_requirement=req_id,
            ))
        elif status == "PARCIAL":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="AU-01_ART45",
                code="AU04-W101",
                message=f"Requisito {req_id} ({title[:60]}) PARCIALMENTE cubierto.",
                recommendation=(
                    f"Completar los elementos faltantes del requisito {req_id}."
                ),
                related_requirement=req_id,
            ))

    # Issues propios del checklist AU-01
    for iss in data.get("issues", []):
        severity_map = {"ERROR": "ALTA", "WARNING": "BAJA"}
        sev = severity_map.get(iss.get("severity", ""), "BAJA")
        issues.append(FinalAuditIssue(
            severity=sev,
            source="AU-01_ART45",
            code=f"AU04-{iss.get('code', 'E100')}",
            message=iss.get("message", ""),
            recommendation=iss.get("recommendation", ""),
            related_requirement=iss.get("requirement_id"),
        ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_prudence
# ---------------------------------------------------------------------------

def extract_final_issues_from_prudence(data: dict | None) -> list[FinalAuditIssue]:
    """Extrae incidencias finales del validador de prudencia (AU-02).

    Si data es None: genera issue AU04-M002 (auditoría faltante → INCOMPLETO).
    Si data corrupta: genera issue ALTA.

    Para cada issue de prudencia:
      ERROR + phrase BLOQUEANTE → BLOQUEANTE
      ERROR otros → ALTA
      WARNING → MEDIA
      INFO → INFO
    """
    if data is None:
        return [FinalAuditIssue(
            severity="ALTA",
            source="SISTEMA",
            code=f"{_MISSING_CODE_PREFIX}002",
            message=(
                "Auditoria AU-02 (Prudencia metodologica) no disponible. "
                "Ejecute 'audit-prudence --write' antes de generar el informe final."
            ),
            recommendation="Ejecutar: python run_expediente.py <exp> audit-prudence --write",
        )]

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="AU-02_PRUDENCE",
            code="AU04-E201",
            message=f"JSON de AU-02 corrupto: {data.get('error', 'error desconocido')}",
            recommendation="Regenerar: python run_expediente.py <exp> audit-prudence --write",
        )]

    issues: list[FinalAuditIssue] = []

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        phrase = iss.get("phrase", "")
        source_file = iss.get("source", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "AU02-E001")

        if raw_sev == "ERROR":
            # Comprobar si es un cierre indebido grave
            is_bloqueante = any(
                bp in phrase.lower() or bp in msg.lower()
                for bp in _BLOQUEANTE_PRUDENCE_PHRASES
            )
            final_sev = "BLOQUEANTE" if is_bloqueante else "ALTA"
            issues.append(FinalAuditIssue(
                severity=final_sev,
                source="AU-02_PRUDENCE",
                code=f"AU04-{code}",
                message=msg or f"Frase imprudente: '{phrase}'",
                recommendation=rec,
                related_file=source_file,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="AU-02_PRUDENCE",
                code=f"AU04-{code}",
                message=msg or f"Lenguaje debil: '{phrase}'",
                recommendation=rec,
                related_file=source_file,
            ))
        elif raw_sev == "INFO":
            issues.append(FinalAuditIssue(
                severity="INFO",
                source="AU-02_PRUDENCE",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_file=source_file,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_traceability
# ---------------------------------------------------------------------------

def extract_final_issues_from_traceability(data: dict | None) -> list[FinalAuditIssue]:
    """Extrae incidencias finales del validador de trazabilidad (AU-03).

    Si data es None: genera issue AU04-M003 (auditoría faltante → INCOMPLETO).
    Si data corrupta: genera issue ALTA.

    Para cada issue de trazabilidad:
      ERROR → ALTA
      WARNING → MEDIA
      INFO → INFO

    Si hay > _UNTRACED_BLOQUEANTE_THRESHOLD afirmaciones no trazadas:
      añade issue BLOQUEANTE.
    """
    if data is None:
        return [FinalAuditIssue(
            severity="ALTA",
            source="SISTEMA",
            code=f"{_MISSING_CODE_PREFIX}003",
            message=(
                "Auditoria AU-03 (Trazabilidad HC <-> DA) no disponible. "
                "Ejecute 'audit-traceability --write' antes del informe final."
            ),
            recommendation=(
                "Ejecutar: python run_expediente.py <exp> audit-traceability --write"
            ),
        )]

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="AU-03_TRACEABILITY",
            code="AU04-E301",
            message=f"JSON de AU-03 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-traceability --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    untraced_claims = data.get("untraced_claims", [])

    # Issue BLOQUEANTE si hay demasiadas afirmaciones sin trazar
    if len(untraced_claims) > _UNTRACED_BLOQUEANTE_THRESHOLD:
        issues.append(FinalAuditIssue(
            severity="BLOQUEANTE",
            source="AU-03_TRACEABILITY",
            code="AU04-E302",
            message=(
                f"Numero elevado de afirmaciones no trazadas: "
                f"{len(untraced_claims)} > {_UNTRACED_BLOQUEANTE_THRESHOLD}. "
                "El Documento Ambiental contiene afirmaciones tecnicas concretas "
                "sin respaldo en las capas de datos del expediente."
            ),
            recommendation=(
                "Revisar las afirmaciones no trazadas e incluir IDs del sistema "
                "(FI-xxx, IMP-xxx, MED-xxx) o los JSONs de origen correspondientes."
            ),
        ))

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        source_file = iss.get("source", "")
        claim = iss.get("claim", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "AU03-E001")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="AU-03_TRACEABILITY",
                code=f"AU04-{code}",
                message=msg or f"Afirmacion no trazada: '{claim[:80]}'",
                recommendation=rec,
                related_file=source_file,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="AU-03_TRACEABILITY",
                code=f"AU04-{code}",
                message=msg or f"Afirmacion parcial: '{claim[:80]}'",
                recommendation=rec,
                related_file=source_file,
            ))
        elif raw_sev == "INFO":
            issues.append(FinalAuditIssue(
                severity="INFO",
                source="AU-03_TRACEABILITY",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_file=source_file,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_block_consistency (RD-04)
# ---------------------------------------------------------------------------

def extract_final_issues_from_block_consistency(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias finales del validador de coherencia entre bloques (RD-04).

    Si data es None: genera issue MEDIA (no INCOMPLETO — RD-04 es optativo).
    Si data corrupta: genera issue ALTA.

    Para cada issue de coherencia:
      ERROR → ALTA
      WARNING → MEDIA
    """
    if data is None:
        # No disponible: no genera issue (solo nota). No cambia status.
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="RD-04_BLOCK_CONSISTENCY",
            code="AU04-E401",
            message=f"JSON de RD-04 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-block-consistency --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="RD-04_BLOCK_CONSISTENCY",
            code="AU04-W402",
            message=(
                "RD-04: sin bloques markdown disponibles para revisar coherencia. "
                "Generar los bloques A-K antes de ejecutar esta auditoria."
            ),
            recommendation=(
                "Ejecutar Fase 7 (redaccion) antes de la auditoria de coherencia."
            ),
        ))
        return issues

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "BC-GEN-001")
        src_block = iss.get("source_block", "")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="RD-04_BLOCK_CONSISTENCY",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_file=src_block or None,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="RD-04_BLOCK_CONSISTENCY",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_file=src_block or None,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_conesa_check (RD-06)
# ---------------------------------------------------------------------------

def extract_final_issues_from_conesa_check(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias finales del checker de cobertura Conesa (RD-06).

    Si data es None: genera issue MEDIA (no INCOMPLETO — RD-06 es optativo).
    Si data corrupta: genera issue ALTA.

    Para cada issue de cobertura Conesa:
      ERROR → ALTA
      WARNING → MEDIA

    Si hay impactos_missing_conesa → ALTA adicional si el modelo existia.
    """
    if data is None:
        # No disponible: no genera issue (solo nota). No cambia status.
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="RD-06_CONESA_CHECK",
            code="AU04-E501",
            message=f"JSON de RD-06 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-conesa --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="RD-06_CONESA_CHECK",
            code="AU04-W502",
            message=(
                "RD-06: sin modelo Phase6 ni markdowns disponibles para cobertura Conesa. "
                "Ejecutar Fase 6 antes de esta auditoria."
            ),
            recommendation="Ejecutar Fase 6 (IM-00 a IM-08) antes de audit-conesa.",
        ))
        return issues

    # Issue ALTA si hay impactos sin Conesa
    missing_conesa = data.get("impacts_missing_conesa", [])
    if missing_conesa:
        issues.append(FinalAuditIssue(
            severity="ALTA",
            source="RD-06_CONESA_CHECK",
            code="AU04-E502",
            message=(
                f"RD-06: {len(missing_conesa)} impacto(s) sin cobertura Conesa "
                f"ni justificacion de indeterminacion: {missing_conesa[:5]}"
            ),
            recommendation=(
                "Completar los atributos Conesa de los impactos o documentar "
                "la razon de indeterminacion (data_gaps o notes)."
            ),
        ))

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "CC-GEN-001")
        imp_id = iss.get("impact_id")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="RD-06_CONESA_CHECK",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="RD-06_CONESA_CHECK",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_diagnostic_measures (RD-08)
# ---------------------------------------------------------------------------

def extract_final_issues_from_diagnostic_measures(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias finales del validador de medidas diagnosticas (RD-08).

    Si data es None: sin issue (RD-08 es optativo — backward compatible).
    Si data corrupta: ALTA.
    SIN_DATOS → MEDIA.
    problematic_measures → ALTA.
    ERROR → ALTA, WARNING → MEDIA.
    """
    if data is None:
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="RD-08_DIAGNOSTIC_MEASURES",
            code="AU04-E601",
            message=f"JSON de RD-08 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-diagnostic-measures --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="RD-08_DIAGNOSTIC_MEASURES",
            code="AU04-W602",
            message=(
                "RD-08: sin modelo de medidas disponible para validar medidas diagnosticas. "
                "Ejecutar Fase 6 antes de esta auditoria."
            ),
            recommendation=(
                "Ejecutar phase6-generate-measures antes de audit-diagnostic-measures."
            ),
        ))
        return issues

    problematic = data.get("problematic_measures", [])
    if problematic:
        issues.append(FinalAuditIssue(
            severity="ALTA",
            source="RD-08_DIAGNOSTIC_MEASURES",
            code="AU04-E603",
            message=(
                f"RD-08: {len(problematic)} medida(s) diagnostica(s) usadas indebidamente "
                f"como reductoras de significancia: {problematic[:5]}"
            ),
            recommendation=(
                "Corregir las medidas diagnosticas para que no afirmen reduccion de "
                "significancia ambiental. Anadir medidas correctoras reales si es necesario."
            ),
        ))

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "RD08-GEN-001")
        m_id = iss.get("measure_id")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="RD-08_DIAGNOSTIC_MEASURES",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=m_id,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="RD-08_DIAGNOSTIC_MEASURES",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=m_id,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_prl_measures (RD-09)
# ---------------------------------------------------------------------------

def extract_final_issues_from_prl_measures(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias finales del validador de separacion EIA/PRL (RD-09).

    Si data es None: sin issue (RD-09 es optativo — backward compatible).
    Si data corrupta: ALTA.
    SIN_DATOS → MEDIA.
    problematic_measures → ALTA.
    ERROR → ALTA, WARNING → MEDIA.
    """
    if data is None:
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="RD-09_PRL_MEASURES",
            code="AU04-E701",
            message=f"JSON de RD-09 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-prl-measures --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="RD-09_PRL_MEASURES",
            code="AU04-W702",
            message=(
                "RD-09: sin modelo de medidas ni markdowns disponibles para validar "
                "la separacion EIA/PRL. Ejecutar Fase 6 antes de esta auditoria."
            ),
            recommendation=(
                "Ejecutar phase6-generate-measures y generar bloques markdown "
                "antes de audit-prl-measures."
            ),
        ))
        return issues

    problematic = data.get("problematic_measures", [])
    if problematic:
        issues.append(FinalAuditIssue(
            severity="ALTA",
            source="RD-09_PRL_MEASURES",
            code="AU04-E703",
            message=(
                f"RD-09: {len(problematic)} medida(s) PRL usadas indebidamente "
                f"como medidas ambientales EIA: {problematic[:5]}"
            ),
            recommendation=(
                "Corregir las medidas PRL para que no aparezcan como reductoras de "
                "significancia ambiental. Declararlas con measure_type='PRL_NO_EIA'."
            ),
        ))

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "RD09-GEN-001")
        m_id = iss.get("measure_id")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="RD-09_PRL_MEASURES",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=m_id,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="RD-09_PRL_MEASURES",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=m_id,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_conditional_chains (IM-09)
# ---------------------------------------------------------------------------

def extract_final_issues_from_conditional_chains(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias finales del validador de cadenas condicionales (IM-09).

    Si data es None: sin issue (IM-09 es optativo — backward compatible).
    Si data corrupta: ALTA.
    SIN_DATOS → MEDIA.
    NO_CONFORME (status) → ALTA si no hay issues individuales que lo expliquen.
    ERROR → ALTA, WARNING → MEDIA.

    Diseño: backward compatible. Los expedientes sin conditional_chain_result.json
    no generan incidencia; solo cuando el archivo existe y tiene errores.
    """
    if data is None:
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="IM-09_CONDITIONAL_CHAINS",
            code="AU04-E801",
            message=f"JSON de IM-09 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-conditional-chains --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="IM-09_CONDITIONAL_CHAINS",
            code="AU04-W802",
            message=(
                "IM-09: sin modelo Phase6 disponible para validar cadenas condicionales. "
                "Ejecutar Fase 6 (IM-00 a IM-09) antes de esta auditoria."
            ),
            recommendation=(
                "Ejecutar phase6-generate-pva antes de audit-conditional-chains."
            ),
        ))
        return issues

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "CC-GEN-001")
        imp_id = iss.get("impact_id")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="IM-09_CONDITIONAL_CHAINS",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="IM-09_CONDITIONAL_CHAINS",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))

    return issues


# ---------------------------------------------------------------------------
# extract_final_issues_from_positive_gaps (RD-07)
# ---------------------------------------------------------------------------

def extract_final_issues_from_positive_gaps(
    data: "dict | None",
) -> "list[FinalAuditIssue]":
    """Extrae incidencias del validador de impactos positivos con gaps ALTA (RD-07).

    None → [] (backward compatible).
    corrupt → ALTA.
    SIN_DATOS → MEDIA.
    ERROR → ALTA, WARNING → MEDIA.
    """
    if data is None:
        return []

    if data.get("corrupt"):
        return [FinalAuditIssue(
            severity="ALTA",
            source="RD-07_POSITIVE_GAPS",
            code="AU04-E901",
            message=f"JSON de RD-07 corrupto: {data.get('error', 'error desconocido')}",
            recommendation=(
                "Regenerar: python run_expediente.py <exp> audit-positive-gaps --write"
            ),
        )]

    issues: list[FinalAuditIssue] = []
    status = data.get("status", "SIN_DATOS")

    if status == "SIN_DATOS":
        issues.append(FinalAuditIssue(
            severity="MEDIA",
            source="RD-07_POSITIVE_GAPS",
            code="AU04-W902",
            message=(
                "RD-07: sin modelo Phase6 disponible para validar impactos positivos con gaps ALTA. "
                "Ejecutar Fase 6 (IM-00 a IM-06) antes de esta auditoria."
            ),
            recommendation="Ejecutar phase6-generate-pva antes de audit-positive-gaps.",
        ))
        return issues

    for iss in data.get("issues", []):
        raw_sev = iss.get("severity", "")
        msg = iss.get("message", "")
        rec = iss.get("recommendation", "")
        code = iss.get("code", "RD07-GEN-001")
        imp_id = iss.get("impact_id")

        if raw_sev == "ERROR":
            issues.append(FinalAuditIssue(
                severity="ALTA",
                source="RD-07_POSITIVE_GAPS",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))
        elif raw_sev == "WARNING":
            issues.append(FinalAuditIssue(
                severity="MEDIA",
                source="RD-07_POSITIVE_GAPS",
                code=f"AU04-{code}",
                message=msg,
                recommendation=rec,
                related_requirement=imp_id,
            ))

    return issues


# ---------------------------------------------------------------------------
# determine_final_audit_status
# ---------------------------------------------------------------------------

def determine_final_audit_status(issues: list[FinalAuditIssue]) -> str:
    """Determina la calificación final a partir de las incidencias consolidadas.

    Prioridad (orden decreciente):
    1. Si alguna incidencia tiene código AU04-M (auditoría faltante) → INCOMPLETO.
    2. Si hay BLOQUEANTE o ALTA → NO_CONFORME.
    3. Si hay MEDIA o BAJA → CONFORME_CON_OBSERVACIONES.
    4. Solo INFO o sin incidencias → CONFORME.
    """
    if any(iss.code.startswith(_MISSING_CODE_PREFIX) for iss in issues):
        return "INCOMPLETO"

    severities = {iss.severity for iss in issues}

    if "BLOQUEANTE" in severities or "ALTA" in severities:
        return "NO_CONFORME"

    if "MEDIA" in severities or "BAJA" in severities:
        return "CONFORME_CON_OBSERVACIONES"

    return "CONFORME"


# ---------------------------------------------------------------------------
# _build_summary_from_art45
# ---------------------------------------------------------------------------

def _build_summary_from_art45(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "covered_count": data.get("covered_count", 0),
        "partial_count": data.get("partial_count", 0),
        "not_covered_count": data.get("not_covered_count", 0),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_structurally_complete": data.get("is_structurally_complete", False),
        "administrative_ready": False,
    }


def _build_summary_from_prudence(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "info_count": data.get("info_count", 0),
        "is_valid": data.get("is_valid", False),
        "checked_sources_count": len(data.get("checked_sources", [])),
    }


def _build_summary_from_traceability(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "traced_count": len(data.get("traced_claims", [])),
        "partial_count": len(data.get("partial_claims", [])),
        "untraced_count": len(data.get("untraced_claims", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("is_valid", False),
        "references_loaded": len(data.get("references_loaded", [])),
    }


def _build_summary_from_diagnostic_measures(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_measures": len(data.get("checked_measures", [])),
        "diagnostic_measures": len(data.get("diagnostic_measures", [])),
        "problematic_measures": len(data.get("problematic_measures", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("error_count", 1) == 0,
    }


def _build_summary_from_prl_measures(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_measures": len(data.get("checked_measures", [])),
        "prl_measures": len(data.get("prl_measures", [])),
        "problematic_measures": len(data.get("problematic_measures", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("error_count", 1) == 0,
    }


def _build_summary_from_conditional_chains(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_impacts": len(data.get("checked_impacts", [])),
        "conditioned_impacts": len(data.get("conditioned_impacts", [])),
        "conditioned_measures": len(data.get("conditioned_measures", [])),
        "conditioned_pva_programs": len(data.get("conditioned_pva_programs", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("error_count", 1) == 0,
    }


def _build_summary_from_positive_gaps(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_impacts": len(data.get("checked_impacts", [])),
        "positive_impacts": len(data.get("positive_impacts", [])),
        "positive_impacts_with_high_gaps": len(data.get("positive_impacts_with_high_gaps", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("error_count", 1) == 0,
    }


def _build_summary_from_block_consistency(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_blocks": len(data.get("checked_blocks", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("is_valid", False),
    }


def _build_summary_from_conesa_check(data: dict | None) -> dict:
    if data is None:
        return {"available": False}
    if data.get("corrupt"):
        return {"available": False, "corrupt": True}
    return {
        "available": True,
        "status": data.get("status", "SIN_DATOS"),
        "checked_impacts": len(data.get("checked_impacts", [])),
        "valued_impacts": len(data.get("valued_impacts", [])),
        "indeterminate_impacts": len(data.get("indeterminate_impacts", [])),
        "impacts_missing_conesa": len(data.get("impacts_missing_conesa", [])),
        "error_count": data.get("error_count", 0),
        "warning_count": data.get("warning_count", 0),
        "is_valid": data.get("is_valid", False),
    }


# ---------------------------------------------------------------------------
# build_final_audit_result
# ---------------------------------------------------------------------------

def build_final_audit_result(
    expediente_id: str,
    art45_data: "dict | None",
    prudence_data: "dict | None",
    traceability_data: "dict | None",
    block_consistency_data: "dict | None" = None,
    conesa_check_data: "dict | None" = None,
    diagnostic_measure_data: "dict | None" = None,
    prl_measure_data: "dict | None" = None,
    conditional_chain_data: "dict | None" = None,
    positive_gap_data: "dict | None" = None,
) -> FinalAuditResult:
    """Construye el resultado final de auditoría combinando AU-01/02/03 + RD-04/06/07/08/09 + IM-09.

    Siempre devuelve un resultado válido. No lanza excepciones.

    Args:
        expediente_id: ID del expediente (nombre del directorio).
        art45_data: dict de art45_checklist_result.json o None.
        prudence_data: dict de prudence_validation_result.json o None.
        traceability_data: dict de traceability_validation_result.json o None.
        block_consistency_data: dict de block_consistency_result.json o None (optativo).
        conesa_check_data: dict de conesa_check_result.json o None (optativo).
        diagnostic_measure_data: dict de diagnostic_measure_validation_result.json o None (optativo).
        prl_measure_data: dict de prl_measure_validation_result.json o None (optativo).
        conditional_chain_data: dict de conditional_chain_result.json o None (optativo).
        positive_gap_data: dict de positive_gap_result.json o None (optativo).

    Returns:
        FinalAuditResult con estado, conteos y lista de incidencias consolidadas.
    """
    all_issues: list[FinalAuditIssue] = []
    all_issues.extend(extract_final_issues_from_art45(art45_data))
    all_issues.extend(extract_final_issues_from_prudence(prudence_data))
    all_issues.extend(extract_final_issues_from_traceability(traceability_data))
    all_issues.extend(extract_final_issues_from_block_consistency(block_consistency_data))
    all_issues.extend(extract_final_issues_from_conesa_check(conesa_check_data))
    all_issues.extend(extract_final_issues_from_diagnostic_measures(diagnostic_measure_data))
    all_issues.extend(extract_final_issues_from_prl_measures(prl_measure_data))
    all_issues.extend(extract_final_issues_from_conditional_chains(conditional_chain_data))
    all_issues.extend(extract_final_issues_from_positive_gaps(positive_gap_data))

    status = determine_final_audit_status(all_issues)

    blocking = sum(1 for i in all_issues if i.severity == "BLOQUEANTE")
    high = sum(1 for i in all_issues if i.severity == "ALTA")
    medium = sum(1 for i in all_issues if i.severity == "MEDIA")
    low = sum(1 for i in all_issues if i.severity == "BAJA")

    _avail = lambda d: "disponible" if d and not d.get("corrupt") else "no disponible"
    notes = [
        "La calificacion es interna y no equivale a aptitud administrativa.",
        f"Estado AU-01: {_avail(art45_data)}.",
        f"Estado AU-02: {_avail(prudence_data)}.",
        f"Estado AU-03: {_avail(traceability_data)}.",
        f"Estado RD-04: {_avail(block_consistency_data)}.",
        f"Estado RD-06: {_avail(conesa_check_data)}.",
        f"Estado RD-07: {_avail(positive_gap_data)}.",
        f"Estado RD-08: {_avail(diagnostic_measure_data)}.",
        f"Estado RD-09: {_avail(prl_measure_data)}.",
        f"Estado IM-09: {_avail(conditional_chain_data)}.",
    ]

    return FinalAuditResult(
        expediente_id=expediente_id,
        status=status,
        administrative_ready=False,
        art45_summary=_build_summary_from_art45(art45_data),
        prudence_summary=_build_summary_from_prudence(prudence_data),
        traceability_summary=_build_summary_from_traceability(traceability_data),
        block_consistency_summary=_build_summary_from_block_consistency(block_consistency_data),
        conesa_check_summary=_build_summary_from_conesa_check(conesa_check_data),
        diagnostic_measure_summary=_build_summary_from_diagnostic_measures(diagnostic_measure_data),
        prl_measure_summary=_build_summary_from_prl_measures(prl_measure_data),
        conditional_chain_summary=_build_summary_from_conditional_chains(conditional_chain_data),
        positive_gap_summary=_build_summary_from_positive_gaps(positive_gap_data),
        issues=all_issues,
        blocking_count=blocking,
        high_count=high,
        medium_count=medium,
        low_count=low,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# build_final_audit_report_markdown
# ---------------------------------------------------------------------------

def build_final_audit_report_markdown(result: FinalAuditResult) -> str:
    """Genera el informe final de auditoría en markdown."""
    lines: list[str] = []

    lines.append("# Informe final de auditoria del expediente")
    lines.append("")

    # ── 1. Resumen ejecutivo ──
    lines.append("## 1. Resumen ejecutivo")
    lines.append("")
    lines.append(f"**Expediente:** {result.expediente_id}")
    lines.append(f"**Calificacion:** {result.status}")
    lines.append(f"**Aptitud administrativa:** NO DECLARADA (`administrative_ready = False`)")
    lines.append("")
    lines.append("| Severidad | Cantidad |")
    lines.append("|-----------|---------|")
    lines.append(f"| BLOQUEANTE | {result.blocking_count} |")
    lines.append(f"| ALTA | {result.high_count} |")
    lines.append(f"| MEDIA | {result.medium_count} |")
    lines.append(f"| BAJA | {result.low_count} |")
    lines.append(f"| **Total incidencias** | **{len(result.issues)}** |")
    lines.append("")

    # ── 2. Resultado AU-01 ──
    lines.append("## 2. Resultado AU-01 — Art.45")
    lines.append("")
    s1 = result.art45_summary
    if not s1.get("available"):
        lines.append("_Auditoria AU-01 no disponible. Ejecute `audit-art45 --write`._")
    else:
        lines.append(f"- Requisitos cubiertos: {s1.get('covered_count', '?')}")
        lines.append(f"- Requisitos parciales: {s1.get('partial_count', '?')}")
        lines.append(f"- Requisitos no cubiertos: {s1.get('not_covered_count', '?')}")
        lines.append(f"- Errores: {s1.get('error_count', '?')}")
        lines.append(
            f"- Estructuralmente completo: {'Si' if s1.get('is_structurally_complete') else 'No'}"
        )
    lines.append("")

    # ── 3. Resultado AU-02 ──
    lines.append("## 3. Resultado AU-02 — Prudencia metodologica")
    lines.append("")
    s2 = result.prudence_summary
    if not s2.get("available"):
        lines.append("_Auditoria AU-02 no disponible. Ejecute `audit-prudence --write`._")
    else:
        lines.append(f"- Fuentes revisadas: {s2.get('checked_sources_count', '?')}")
        lines.append(f"- Incidencias ERROR: {s2.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s2.get('warning_count', '?')}")
        lines.append(f"- Resultado: {'VALIDO' if s2.get('is_valid') else 'NO VALIDO'}")
    lines.append("")

    # ── 4. Resultado AU-03 ──
    lines.append("## 4. Resultado AU-03 — Trazabilidad HC <-> DA")
    lines.append("")
    s3 = result.traceability_summary
    if not s3.get("available"):
        lines.append(
            "_Auditoria AU-03 no disponible. Ejecute `audit-traceability --write`._"
        )
    else:
        lines.append(f"- Referencias cargadas: {s3.get('references_loaded', '?')}")
        lines.append(f"- Afirmaciones trazadas: {s3.get('traced_count', '?')}")
        lines.append(f"- Afirmaciones parciales: {s3.get('partial_count', '?')}")
        lines.append(f"- Afirmaciones no trazadas: {s3.get('untraced_count', '?')}")
        lines.append(f"- Resultado: {'VALIDO' if s3.get('is_valid') else 'NO VALIDO'}")
    lines.append("")

    # ── 5. Resultado RD-04 ──
    lines.append("## 5. Resultado RD-04 — Coherencia entre bloques")
    lines.append("")
    s4 = result.block_consistency_summary
    if not s4.get("available"):
        lines.append(
            "_Auditoria RD-04 no disponible. Ejecute `audit-block-consistency --write`._"
        )
    else:
        lines.append(f"- Estado: {s4.get('status', '?')}")
        lines.append(f"- Bloques revisados: {s4.get('checked_blocks', '?')}")
        lines.append(f"- Incidencias ERROR: {s4.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s4.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'COHERENTE' if s4.get('is_valid') else 'CON INCIDENCIAS'}"
        )
    lines.append("")

    # ── 6. Resultado RD-06 ──
    lines.append("## 6. Resultado RD-06 — Cobertura Conesa")
    lines.append("")
    s5 = result.conesa_check_summary
    if not s5.get("available"):
        lines.append(
            "_Auditoria RD-06 no disponible. Ejecute `audit-conesa --write`._"
        )
    else:
        lines.append(f"- Estado: {s5.get('status', '?')}")
        lines.append(f"- Impactos revisados: {s5.get('checked_impacts', '?')}")
        lines.append(f"- Sin Conesa completo: {s5.get('impacts_missing_conesa', '?')}")
        lines.append(f"- Incidencias ERROR: {s5.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s5.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'CONFORME' if s5.get('is_valid') else 'NO CONFORME'}"
        )
    lines.append("")

    # ── 7. Resultado RD-08 ──
    lines.append("## 7. Resultado RD-08 — Medidas diagnosticas vs reductoras")
    lines.append("")
    s6 = result.diagnostic_measure_summary
    if not s6.get("available"):
        lines.append(
            "_Auditoria RD-08 no disponible. Ejecute `audit-diagnostic-measures --write`._"
        )
    else:
        lines.append(f"- Estado: {s6.get('status', '?')}")
        lines.append(f"- Medidas revisadas: {s6.get('checked_measures', '?')}")
        lines.append(f"- Medidas diagnosticas: {s6.get('diagnostic_measures', '?')}")
        lines.append(f"- Con incidencias: {s6.get('problematic_measures', '?')}")
        lines.append(f"- Incidencias ERROR: {s6.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s6.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'CONFORME' if s6.get('is_valid') else 'NO CONFORME'}"
        )
    lines.append("")

    # ── 8. Resultado RD-09 ──
    lines.append("## 8. Resultado RD-09 — Separacion EIA / PRL")
    lines.append("")
    s7 = result.prl_measure_summary
    if not s7.get("available"):
        lines.append(
            "_Auditoria RD-09 no disponible. Ejecute `audit-prl-measures --write`._"
        )
    else:
        lines.append(f"- Estado: {s7.get('status', '?')}")
        lines.append(f"- Medidas revisadas: {s7.get('checked_measures', '?')}")
        lines.append(f"- Medidas PRL: {s7.get('prl_measures', '?')}")
        lines.append(f"- Con incidencias: {s7.get('problematic_measures', '?')}")
        lines.append(f"- Incidencias ERROR: {s7.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s7.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'CONFORME' if s7.get('is_valid') else 'NO CONFORME'}"
        )
    lines.append("")

    # ── 9. Resultado RD-07 ──
    lines.append("## 9. Resultado RD-07 — Impactos positivos con gaps ALTA")
    lines.append("")
    s9 = result.positive_gap_summary
    if not s9.get("available"):
        lines.append(
            "_Auditoria RD-07 no disponible. Ejecute `audit-positive-gaps --write`._"
        )
    else:
        lines.append(f"- Estado: {s9.get('status', '?')}")
        lines.append(f"- Impactos revisados: {s9.get('checked_impacts', '?')}")
        lines.append(f"- Impactos positivos: {s9.get('positive_impacts', '?')}")
        lines.append(
            f"- Positivos con gap ALTA: {s9.get('positive_impacts_with_high_gaps', '?')}"
        )
        lines.append(f"- Incidencias ERROR: {s9.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s9.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'CONFORME' if s9.get('is_valid') else 'NO CONFORME'}"
        )
    lines.append("")

    # ── 10. Resultado IM-09 ──
    lines.append("## 10. Resultado IM-09 — Cadenas condicionales impacto-medida-PVA")
    lines.append("")
    s8 = result.conditional_chain_summary
    if not s8.get("available"):
        lines.append(
            "_Auditoria IM-09 no disponible. Ejecute `audit-conditional-chains --write`._"
        )
    else:
        lines.append(f"- Estado: {s8.get('status', '?')}")
        lines.append(f"- Impactos revisados: {s8.get('checked_impacts', '?')}")
        lines.append(f"- Impactos condicionados: {s8.get('conditioned_impacts', '?')}")
        lines.append(f"- Medidas condicionadas: {s8.get('conditioned_measures', '?')}")
        lines.append(f"- PVA condicionados: {s8.get('conditioned_pva_programs', '?')}")
        lines.append(f"- Incidencias ERROR: {s8.get('error_count', '?')}")
        lines.append(f"- Incidencias WARNING: {s8.get('warning_count', '?')}")
        lines.append(
            f"- Resultado: {'CONFORME' if s8.get('is_valid') else 'NO CONFORME'}"
        )
    lines.append("")

    # ── 11. Incidencias BLOQUEANTE ──
    lines.append("## 11. Incidencias bloqueantes")
    lines.append("")
    blockers = [i for i in result.issues if i.severity == "BLOQUEANTE"]
    if blockers:
        for iss in blockers:
            lines.append(f"**[{iss.code}]** ({iss.source})")
            lines.append(f"  {iss.message}")
            lines.append(f"  > {iss.recommendation}")
            lines.append("")
    else:
        lines.append("_Sin incidencias BLOQUEANTE._")
        lines.append("")

    # ── 12. Incidencias ALTA ──
    lines.append("## 12. Incidencias altas")
    lines.append("")
    highs = [i for i in result.issues if i.severity == "ALTA"]
    if highs:
        for iss in highs[:10]:
            req = f" — {iss.related_requirement}" if iss.related_requirement else ""
            lines.append(f"**[{iss.code}]** ({iss.source}){req}")
            lines.append(f"  {iss.message[:120]}")
            lines.append("")
        if len(highs) > 10:
            lines.append(f"_... y {len(highs)-10} incidencias ALTA adicionales._")
            lines.append("")
    else:
        lines.append("_Sin incidencias ALTA._")
        lines.append("")

    # ── 13. Incidencias MEDIA y BAJA ──
    lines.append("## 13. Incidencias medias y bajas")
    lines.append("")
    mid_low = [i for i in result.issues if i.severity in ("MEDIA", "BAJA")]
    if mid_low:
        for iss in mid_low[:15]:
            lines.append(f"- [{iss.severity}] [{iss.code}] {iss.message[:100]}")
        if len(mid_low) > 15:
            lines.append(f"- ... y {len(mid_low)-15} incidencias adicionales.")
    else:
        lines.append("_Sin incidencias MEDIA ni BAJA._")
    lines.append("")

    # ── 14. Recomendaciones prioritarias ──
    lines.append("## 14. Recomendaciones prioritarias")
    lines.append("")
    priority_issues = [
        i for i in result.issues if i.severity in ("BLOQUEANTE", "ALTA")
    ]
    if priority_issues:
        seen_recs: set[str] = set()
        for iss in priority_issues[:8]:
            rec = iss.recommendation[:120]
            if rec not in seen_recs:
                seen_recs.add(rec)
                lines.append(f"- {rec}")
    else:
        lines.append(
            "- Revisar las incidencias MEDIA y BAJA para mejorar la calidad del expediente."
        )
    lines.append("")

    # ── 15. Conclusión final ──
    lines.append("## 15. Conclusion final")
    lines.append("")
    status_descriptions = {
        "CONFORME": (
            "El expediente supera las verificaciones internas de AU-01, AU-02, AU-03, "
            "RD-04, RD-06, RD-07, RD-08, RD-09 e IM-09 sin incidencias de severidad ALTA o BLOQUEANTE."
        ),
        "CONFORME_CON_OBSERVACIONES": (
            "El expediente presenta observaciones de severidad MEDIA o BAJA que deben "
            "atenderse antes de la presentacion. No hay incidencias ALTA ni BLOQUEANTE."
        ),
        "NO_CONFORME": (
            "El expediente presenta incidencias de severidad ALTA o BLOQUEANTE que "
            "deben resolverse antes de proceder con las fases siguientes."
        ),
        "INCOMPLETO": (
            "Una o mas auditorias (AU-01, AU-02, AU-03) no han sido ejecutadas. "
            "Ejecute todas las auditorias antes de generar el informe final."
        ),
    }
    lines.append(status_descriptions.get(result.status, "Estado desconocido."))
    lines.append("")
    lines.append(
        "> **Este informe no declara el expediente apto para presentación administrativa. "
        "La calificación es interna y no equivale a resolución del órgano ambiental. "
        "La aptitud administrativa del expediente la determina el órgano competente.**"
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_final_audit_from_files
# ---------------------------------------------------------------------------

def build_final_audit_from_files(
    expediente_path: "str | Path",
) -> FinalAuditResult:
    """Construye el informe final leyendo los JSONs de auditoría del expediente.

    Busca en `auditoria/`:
      - art45_checklist_result.json
      - prudence_validation_result.json
      - traceability_validation_result.json

    No lanza excepción por ausencia de archivos individuales.
    Genera resultado INCOMPLETO si falta alguna auditoría.

    Args:
        expediente_path: Ruta al directorio del expediente EIA.

    Raises:
        FileNotFoundError: si el directorio del expediente no existe.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(
            f"Directorio de expediente no encontrado: {exp_path}"
        )

    auditoria_dir = exp_path / "auditoria"
    art45_data = load_audit_json(auditoria_dir / "art45_checklist_result.json")
    prudence_data = load_audit_json(auditoria_dir / "prudence_validation_result.json")
    traceability_data = load_audit_json(
        auditoria_dir / "traceability_validation_result.json"
    )
    block_consistency_data = load_audit_json(
        auditoria_dir / "block_consistency_result.json"
    )
    conesa_check_data = load_audit_json(
        auditoria_dir / "conesa_check_result.json"
    )
    diagnostic_measure_data = load_audit_json(
        auditoria_dir / "diagnostic_measure_validation_result.json"
    )
    prl_measure_data = load_audit_json(
        auditoria_dir / "prl_measure_validation_result.json"
    )
    conditional_chain_data = load_audit_json(
        auditoria_dir / "conditional_chain_result.json"
    )
    positive_gap_data = load_audit_json(
        auditoria_dir / "positive_gap_result.json"
    )

    return build_final_audit_result(
        expediente_id=exp_path.name,
        art45_data=art45_data,
        prudence_data=prudence_data,
        traceability_data=traceability_data,
        block_consistency_data=block_consistency_data,
        conesa_check_data=conesa_check_data,
        diagnostic_measure_data=diagnostic_measure_data,
        prl_measure_data=prl_measure_data,
        conditional_chain_data=conditional_chain_data,
        positive_gap_data=positive_gap_data,
    )


# ---------------------------------------------------------------------------
# write_final_audit_outputs
# ---------------------------------------------------------------------------

def write_final_audit_outputs(
    result: FinalAuditResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs del informe final de auditoría.

    Escribe:
      - {output_dir}/final_audit_result.json
      - {output_dir}/final_audit_result.md

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "final_audit_result.json"
    md_path = output_dir / "final_audit_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_final_audit_report_markdown(result))

    return json_path, md_path
