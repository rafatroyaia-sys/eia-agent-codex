"""
art45_checklist -- AU-01
Checklist programático del art. 45.1 Ley 21/2013 para EIA simplificada.

Evalúa si un expediente tiene cobertura suficiente para los contenidos mínimos
del Documento Ambiental según el art. 45.1 de la Ley 21/2013, de 9 de
diciembre, de evaluación ambiental.

Advertencia de alcance (obligatoria):
  Este checklist es una verificación estructural interna. No declara
  aptitud administrativa ni sustituye revisión técnica o jurídica.
  No revisa legislación autonómica específica (BOC, normativa Canarias, etc.).
  La clasificación final del expediente corresponde al órgano ambiental.

Principios no negociables:
  - No usa IA.
  - No consulta fuentes externas.
  - No modifica el expediente.
  - administrative_ready siempre False.
  - No sustituye la revisión del órgano ambiental.
  - Los estados CUBIERTO/PARCIAL/NO_CUBIERTO son internos: no tienen
    valor jurídico definitivo.

Dependencias: IM-00 (impact_model) — solo para tipado de Phase6Model.
"""
from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.impact_model import Phase6Model

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ascii_safe(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return nfkd.encode("ascii", "ignore").decode("ascii")


# ---------------------------------------------------------------------------
# Constantes del dominio
# ---------------------------------------------------------------------------

COVERAGE_STATUS: list[str] = ["CUBIERTO", "PARCIAL", "NO_CUBIERTO", "NO_APLICA"]
ISSUE_SEVERITY: list[str] = ["ERROR", "WARNING", "INFO"]

# Requisitos mínimos del art. 45.1 Ley 21/2013 (EIA simplificada)
ART45_REQUIREMENTS: list[dict] = [
    {
        "requirement_id": "ART45-01",
        "title": "Motivacion de la aplicacion del procedimiento de EIA simplificada",
        "description": (
            "El Documento Ambiental debe incluir la motivacion por la que el proyecto "
            "se somete a EIA simplificada conforme al Anexo II o IV de la Ley 21/2013."
        ),
    },
    {
        "requirement_id": "ART45-02",
        "title": "Definicion, caracteristicas y ubicacion del proyecto",
        "description": (
            "Descripcion suficiente del proyecto: actividades, operaciones, titular, "
            "referencia catastral, coordenadas, superficie y ubicacion cartografica."
        ),
    },
    {
        "requirement_id": "ART45-03",
        "title": "Exposicion de alternativas estudiadas y justificacion de solucion adoptada",
        "description": (
            "Al menos la alternativa cero y la alternativa elegida deben estar "
            "justificadas en el Documento Ambiental."
        ),
    },
    {
        "requirement_id": "ART45-04",
        "title": "Evaluacion de efectos previsibles directos e indirectos",
        "description": (
            "Identificacion y, cuando sea posible, valoracion de los efectos sobre "
            "los factores ambientales receptores."
        ),
    },
    {
        "requirement_id": "ART45-05",
        "title": "Efectos acumulativos y sinergicos",
        "description": (
            "Analisis de los efectos acumulativos y sinergicos con otras actividades "
            "o proyectos del entorno, conforme al art. 45.1.f) Ley 21/2013."
        ),
    },
    {
        "requirement_id": "ART45-06",
        "title": "Factores ambientales afectados",
        "description": (
            "Poblacion y salud humana, flora, fauna, biodiversidad, suelo, agua, aire, "
            "factores climaticos, cambio climatico, paisaje, bienes materiales, "
            "patrimonio cultural e interaccion entre factores."
        ),
    },
    {
        "requirement_id": "ART45-07",
        "title": "Medidas para prevenir, reducir y corregir efectos adversos",
        "description": (
            "Medidas preventivas, correctoras y compensatorias previstas para eliminar "
            "o reducir los efectos adversos identificados."
        ),
    },
    {
        "requirement_id": "ART45-08",
        "title": "Programa de seguimiento y vigilancia ambiental",
        "description": (
            "Cuando proceda, el Documento Ambiental debe incluir el Programa de "
            "Vigilancia Ambiental con indicadores, umbrales y responsable."
        ),
    },
    {
        "requirement_id": "ART45-09",
        "title": "Vulnerabilidad ante riesgos de accidentes graves o catastrofes",
        "description": (
            "Evaluacion de la vulnerabilidad del proyecto ante riesgos naturales, "
            "si procede segun la naturaleza y ubicacion del proyecto."
        ),
    },
    {
        "requirement_id": "ART45-10",
        "title": "Cartografia y ubicacion suficiente",
        "description": (
            "Planos y cartografia suficientes para identificar el emplazamiento, "
            "las afecciones y el area de estudio."
        ),
    },
    {
        "requirement_id": "ART45-11",
        "title": "Incertidumbres, gaps y limitaciones declaradas",
        "description": (
            "Las dificultades, incertidumbres tecnicas y limitaciones de la informacion "
            "deben declararse explicitamente, no absorberse en el texto."
        ),
    },
    {
        "requirement_id": "ART45-12",
        "title": "Resumen no tecnico o base para generarlo",
        "description": (
            "El Documento Ambiental debe incluir o permitir generar un resumen "
            "no tecnico comprensible para el publico en general."
        ),
    },
]

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Art45ChecklistItem:
    """Resultado de evaluación de un requisito del art. 45.1 Ley 21/2013."""

    requirement_id: str
    """ART45-01 … ART45-12."""

    title: str
    """Título del requisito."""

    status: str
    """CUBIERTO / PARCIAL / NO_CUBIERTO / NO_APLICA."""

    evidence_refs: list[str] = field(default_factory=list)
    """Evidencias encontradas que soportan el estado."""

    missing_elements: list[str] = field(default_factory=list)
    """Elementos que faltan para alcanzar CUBIERTO."""

    notes: list[str] = field(default_factory=list)
    """Notas de trazabilidad del evaluador."""

    def to_dict(self) -> dict:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "status": self.status,
            "evidence_refs": list(self.evidence_refs),
            "missing_elements": list(self.missing_elements),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        s = f"[{self.status:12s}] {self.requirement_id} — {self.title[:60]}"
        return _ascii_safe(s)


@dataclass
class Art45ChecklistIssue:
    """Incidencia del checklist art. 45."""

    severity: str
    """ERROR / WARNING / INFO."""

    code: str
    """Código de la incidencia (ej. AU01-E001)."""

    requirement_id: Optional[str]
    """Requisito afectado, o None si es global."""

    message: str
    """Descripción de la incidencia."""

    recommendation: str
    """Acción recomendada."""

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "requirement_id": self.requirement_id,
            "message": self.message,
            "recommendation": self.recommendation,
        }

    def summary(self) -> str:
        parts = [f"[{self.severity}]", self.code]
        if self.requirement_id:
            parts.append(f"({self.requirement_id})")
        parts.append(self.message[:80] + ("..." if len(self.message) > 80 else ""))
        return _ascii_safe(" ".join(parts))


@dataclass
class Art45ChecklistResult:
    """Resultado completo del checklist art. 45.1 Ley 21/2013."""

    expediente_id: str
    items: list[Art45ChecklistItem] = field(default_factory=list)
    issues: list[Art45ChecklistIssue] = field(default_factory=list)
    administrative_ready: bool = False
    """Siempre False. AU-01 no declara aptitud administrativa."""
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def covered_count(self) -> int:
        return sum(1 for i in self.items if i.status == "CUBIERTO")

    def partial_count(self) -> int:
        return sum(1 for i in self.items if i.status == "PARCIAL")

    def not_covered_count(self) -> int:
        return sum(1 for i in self.items if i.status == "NO_CUBIERTO")

    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    def is_structurally_complete(self) -> bool:
        """True si no hay NO_CUBIERTO y no hay ERRORs."""
        return self.not_covered_count() == 0 and self.error_count() == 0

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "items": [i.to_dict() for i in self.items],
            "issues": [i.to_dict() for i in self.issues],
            "administrative_ready": self.administrative_ready,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
            "covered_count": self.covered_count(),
            "partial_count": self.partial_count(),
            "not_covered_count": self.not_covered_count(),
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "is_structurally_complete": self.is_structurally_complete(),
        }

    def summary(self) -> str:
        lines = [
            "--- AU-01 Checklist art. 45.1 Ley 21/2013 ---",
            f"Expediente         : {_ascii_safe(self.expediente_id)}",
            f"CUBIERTO           : {self.covered_count()}/12",
            f"PARCIAL            : {self.partial_count()}/12",
            f"NO CUBIERTO        : {self.not_covered_count()}/12",
            f"ERRORs             : {self.error_count()}",
            f"WARNINGs           : {self.warning_count()}",
            f"Completo (estruct.): {'SI' if self.is_structurally_complete() else 'NO'}",
            "administrative_ready: SIEMPRE FALSE (AU-01 no declara aptitud)",
        ]
        if self.not_covered_count() > 0:
            nc = [i.requirement_id for i in self.items if i.status == "NO_CUBIERTO"]
            lines.append("  NO CUBIERTO: " + ", ".join(nc))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Función de evaluación principal
# ---------------------------------------------------------------------------

def evaluate_art45_checklist_from_model(
    expediente_id: str,
    phase6_model: Optional[Phase6Model] = None,
    phase5_gate_result: Optional[dict] = None,
    cumulative_result: Optional[dict] = None,
    pva_coverage_result: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> Art45ChecklistResult:
    """Evalúa el checklist art.45.1 desde un Phase6Model y resultados de fases.

    Reglas de evaluación (CUBIERTO/PARCIAL/NO_CUBIERTO/NO_APLICA):
      Ver docstring de cada evaluador interno.

    Parámetros opcionales:
      phase6_model: Phase6Model con impactos, medidas, PVA.
      phase5_gate_result: dict del gate de Fase 5 (inventario).
      cumulative_result: dict del resultado IM-08 (C.5 acumulativos).
      pva_coverage_result: dict del resultado IM-07 (cobertura PVA).
      metadata: dict con claves opcionales:
        - procedure_motivation (str): motivación del procedimiento
        - alternatives_analysis (str/bool): alternativas estudiadas
        - alternativa_cero (bool): si se incluye al menos la alternativa cero
        - justificacion_solucion (str): justificación de la solución adoptada
        - object_scope (dict): ficha del objeto evaluado (Fase 2)
        - cartography_plan (dict/bool): plan cartográfico
        - mapas (list): lista de mapas disponibles
        - non_technical_summary (str/bool): resumen no técnico

    No modifica el expediente. No declara aptitud administrativa.
    administrative_ready siempre False.
    """
    meta = metadata or {}
    m = phase6_model

    items: list[Art45ChecklistItem] = []
    issues: list[Art45ChecklistIssue] = []

    # ── ART45-01: Motivación del procedimiento ──────────────────────────
    ev = []
    miss = []
    if meta.get("procedure_motivation"):
        status01 = "CUBIERTO"
        ev.append("metadata.procedure_motivation presente")
    elif phase5_gate_result or meta.get("object_scope") or meta.get("phase3_result"):
        status01 = "PARCIAL"
        ev.append("Fase 3 / triaje normativo detectado")
        miss.append("Texto explícito de motivacion del procedimiento EIA simplificada")
    else:
        status01 = "NO_CUBIERTO"
        miss.append("Motivacion del procedimiento (campo procedure_motivation o triaje normativo)")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-01", title=ART45_REQUIREMENTS[0]["title"],
        status=status01, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar que el Bloque A incluye la motivacion del procedimiento."],
    ))

    # ── ART45-02: Definición y ubicación del proyecto ───────────────────
    ev = []
    miss = []
    has_actions = bool(m and m.actions)
    has_scope = bool(meta.get("object_scope") or phase5_gate_result)
    has_coords = bool(meta.get("object_scope", {}).get("coordinates") if isinstance(meta.get("object_scope"), dict) else False)

    if has_actions and has_scope:
        status02 = "CUBIERTO"
        ev.append(f"Phase6Model con {len(m.actions)} accion(es)")
        ev.append("object_scope / phase5_gate detectado")
    elif has_actions:
        status02 = "PARCIAL"
        ev.append(f"Phase6Model con {len(m.actions)} accion(es)")
        miss.append("Ficha objeto evaluado (coordenadas, RC, superficie) no confirmada")
    else:
        status02 = "NO_CUBIERTO"
        miss.append("Actions del proyecto (phase6_model.actions vacio)")
        miss.append("Ubicacion y caracteristicas del proyecto")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-02", title=ART45_REQUIREMENTS[1]["title"],
        status=status02, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque A (identificacion y descripcion del proyecto)."],
    ))

    # ── ART45-03: Alternativas ──────────────────────────────────────────
    ev = []
    miss = []
    if meta.get("alternatives_analysis"):
        status03 = "CUBIERTO"
        ev.append("metadata.alternatives_analysis presente")
    elif meta.get("alternativa_cero") or meta.get("justificacion_solucion"):
        status03 = "PARCIAL"
        if meta.get("alternativa_cero"):
            ev.append("alternativa_cero declarada")
        if meta.get("justificacion_solucion"):
            ev.append("justificacion_solucion declarada")
        miss.append("Analisis completo de alternativas (minimo: alternativa cero + elegida)")
    else:
        status03 = "NO_CUBIERTO"
        miss.append("Alternativas estudiadas (metadata.alternatives_analysis)")
        miss.append("Al menos: alternativa cero + alternativa elegida con justificacion")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-03", title=ART45_REQUIREMENTS[2]["title"],
        status=status03, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque F (alternativas). Minimo: alternativa cero + solucion adoptada."],
    ))

    # ── ART45-04: Efectos directos e indirectos ─────────────────────────
    ev = []
    miss = []
    has_impacts = bool(m and m.impacts)
    has_receptors = bool(m and m.receptor_factors)
    if has_impacts:
        n_valorado = sum(1 for i in m.impacts if i.status == "VALORADO")
        n_total = len(m.impacts)
        status04 = "CUBIERTO"
        ev.append(f"{n_total} impacto(s) identificados, {n_valorado} valorados")
    elif has_receptors:
        status04 = "PARCIAL"
        ev.append(f"Phase6Model con {len(m.receptor_factors)} receptor(es) pero sin impactos")
        miss.append("Identificacion y valoracion de impactos (phase6_model.impacts vacio)")
    else:
        status04 = "NO_CUBIERTO"
        miss.append("Modelo de impactos (phase6_model sin impacts ni receptor_factors)")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-04", title=ART45_REQUIREMENTS[3]["title"],
        status=status04, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque C (impactos). Seccion C.1-C.4."],
    ))

    # ── ART45-05: Acumulativos/sinérgicos ───────────────────────────────
    ev = []
    miss = []
    has_cumul_result = bool(
        cumulative_result
        and (
            cumulative_result.get("markdown")
            or cumulative_result.get("cumulative_groups")
            or cumulative_result.get("synergistic_groups")
        )
    )
    if has_cumul_result:
        n_cumul = len(cumulative_result.get("cumulative_groups", {}))
        n_syn = len(cumulative_result.get("synergistic_groups", {}))
        status05 = "CUBIERTO"
        ev.append(f"cumulative_result presente: {n_cumul} acumulativos, {n_syn} sinergicos")
    elif has_impacts:
        status05 = "PARCIAL"
        ev.append("Impactos identificados pero sin seccion C.5 generada")
        miss.append("Seccion C.5 (efectos acumulativos y sinergicos) — ejecutar phase6-cumulative")
    else:
        status05 = "NO_CUBIERTO"
        miss.append("Impactos y seccion C.5 de efectos acumulativos y sinergicos")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-05", title=ART45_REQUIREMENTS[4]["title"],
        status=status05, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque C seccion C.5. Requerido por art. 45.1.f) Ley 21/2013."],
    ))

    # ── ART45-06: Factores ambientales ──────────────────────────────────
    ev = []
    miss = []
    n_factors = len(m.receptor_factors) if m else 0
    n_gate_factors = 0
    if phase5_gate_result:
        n_gate_factors = phase5_gate_result.get("total_factors", 0)
    n_eff_factors = max(n_factors, n_gate_factors)

    if n_eff_factors >= 16:
        status06 = "CUBIERTO"
        ev.append(f"{n_eff_factors} factores ambientales cubiertos (FI-001…FI-016)")
    elif n_eff_factors > 0:
        status06 = "PARCIAL"
        ev.append(f"{n_eff_factors} factores detectados (se esperan 16)")
        miss.append(f"Factores ambientales faltantes ({16 - n_eff_factors} sin datos)")
    else:
        status06 = "NO_CUBIERTO"
        miss.append("Factores ambientales del inventario (FI-001…FI-016)")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-06", title=ART45_REQUIREMENTS[5]["title"],
        status=status06, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque B (inventario ambiental) y Phase6Model.receptor_factors."],
    ))

    # ── ART45-07: Medidas ───────────────────────────────────────────────
    ev = []
    miss = []
    has_measures = bool(m and m.measures)
    if has_measures:
        n_med = len(m.measures)
        n_prl = sum(1 for med in m.measures if med.is_prl_only)
        n_diag = sum(1 for med in m.measures if med.is_diagnostic)
        n_env = n_med - n_prl - n_diag
        status07 = "CUBIERTO"
        ev.append(f"{n_med} medida(s): {n_env} ambientales, {n_diag} diagnosticas, {n_prl} PRL")
    elif has_impacts:
        status07 = "PARCIAL"
        ev.append(f"{len(m.impacts)} impacto(s) sin medidas generadas")
        miss.append("Medidas ambientales (phase6_model.measures vacio) — ejecutar phase6-generate-measures")
    else:
        status07 = "NO_CUBIERTO"
        miss.append("Impactos y medidas preventivas/correctoras")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-07", title=ART45_REQUIREMENTS[6]["title"],
        status=status07, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque D (medidas). Distinguir EIA vs PRL_NO_EIA."],
    ))

    # ── ART45-08: Seguimiento/PVA ────────────────────────────────────────
    ev = []
    miss = []
    has_pva = bool(m and m.pva_programs)
    pva_is_valid = bool(
        pva_coverage_result
        and pva_coverage_result.get("is_valid", False)
    )
    pva_has_warnings = bool(
        pva_coverage_result
        and pva_coverage_result.get("warning_count", 0) > 0
    )

    if has_pva and pva_is_valid:
        status08 = "CUBIERTO"
        n_pva = len(m.pva_programs)
        ev.append(f"{n_pva} ficha(s) PVA, cobertura valida (IM-07)")
    elif has_pva and pva_has_warnings:
        status08 = "PARCIAL"
        ev.append(f"{len(m.pva_programs)} ficha(s) PVA con cobertura condicional o parcial")
        miss.append("Completar cobertura PVA (revisar warnings de IM-07)")
    elif has_pva:
        status08 = "PARCIAL"
        ev.append(f"{len(m.pva_programs)} ficha(s) PVA (cobertura no verificada por IM-07)")
        miss.append("Ejecutar phase6-validate-pva para verificar cobertura")
    else:
        status08 = "NO_CUBIERTO"
        miss.append("Programa de Vigilancia Ambiental (phase6_model.pva_programs vacio)")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-08", title=ART45_REQUIREMENTS[7]["title"],
        status=status08, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque E (PVA). Responsable Ambiental pendiente de designar."],
    ))

    # ── ART45-09: Vulnerabilidad/riesgos ────────────────────────────────
    ev = []
    miss = []
    # Buscar FR-016 (Riesgos naturales) en receptor_factors o FI-016 en inventario
    has_risks_receptor = bool(
        m and any(r.receptor_id in ("FR-016", "FR-005") for r in m.receptor_factors)
    )
    has_risks_impact = bool(
        m and any(imp.receptor_id in ("FR-016", "FR-005") for imp in m.impacts)
    )
    has_risks_gate = bool(
        phase5_gate_result and phase5_gate_result.get("total_factors", 0) >= 16
    )

    if has_risks_impact:
        status09 = "CUBIERTO"
        ev.append("FR-016 (Riesgos naturales) con impactos identificados")
    elif has_risks_receptor or has_risks_gate:
        status09 = "PARCIAL"
        ev.append("FR-016/FR-005 en receptores pero sin impactos valorados")
        miss.append("Evaluacion de vulnerabilidad ante riesgos naturales en impactos")
    else:
        status09 = "PARCIAL"
        ev.append("No se puede confirmar cobertura de riesgos naturales")
        miss.append("Verificar cobertura de FR-016 (Riesgos naturales) y FI-005 (Inundabilidad)")
        notes09 = ["Si el proyecto no esta en zona de riesgo, justificar NO_APLICA."]
    items.append(Art45ChecklistItem(
        requirement_id="ART45-09", title=ART45_REQUIREMENTS[8]["title"],
        status=status09, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque G (vulnerabilidad). FR-016 / FI-005."],
    ))

    # ── ART45-10: Cartografía ────────────────────────────────────────────
    ev = []
    miss = []
    has_carto_plan = bool(meta.get("cartography_plan"))
    has_mapas = bool(meta.get("mapas"))
    has_scope_coords = bool(meta.get("object_scope"))

    if has_carto_plan or has_mapas:
        status10 = "CUBIERTO"
        if has_carto_plan:
            ev.append("cartography_plan detectado")
        if has_mapas:
            ev.append(f"{len(meta['mapas'])} mapa(s) disponibles")
    elif has_scope_coords:
        status10 = "PARCIAL"
        ev.append("object_scope con coordenadas detectado")
        miss.append("Cartografia con mapas de situacion, emplazamiento y afecciones")
    else:
        status10 = "NO_CUBIERTO"
        miss.append("Plan cartografico (phase6-cumulative o cartography-plan)")
        miss.append("Mapas de situacion, emplazamiento, Red Natura 2000, usos del suelo")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-10", title=ART45_REQUIREMENTS[9]["title"],
        status=status10, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar cartografia/ con mapas MAP-001 a MAP-008 minimos."],
    ))

    # ── ART45-11: Incertidumbres/gaps ────────────────────────────────────
    ev = []
    miss = []
    # Gaps en el modelo de impactos
    model_gaps = []
    if m:
        model_gaps = list({
            g for imp in m.impacts for g in imp.data_gaps
        })
    gate_gaps = []
    if phase5_gate_result:
        gate_gaps = phase5_gate_result.get("issue_codes", [])
    cumul_gaps = []
    if cumulative_result:
        cumul_gaps = cumulative_result.get("unresolved_gaps", [])
    all_gaps = list(set(model_gaps + gate_gaps + cumul_gaps))

    if all_gaps:
        status11 = "CUBIERTO"
        ev.append(f"{len(all_gaps)} gap(s) documentados en el expediente")
    elif m and m.warnings:
        status11 = "PARCIAL"
        ev.append(f"{len(m.warnings)} aviso(s) en el modelo pero sin gaps formales")
        miss.append("Gaps formales declarados con ID en data_gaps de impactos o inventario")
    elif phase5_gate_result or (m and m.impacts):
        status11 = "PARCIAL"
        ev.append("Impactos o inventario presente pero sin gaps documentados")
        miss.append("Declaracion explicita de incertidumbres y gaps (data_gaps en impactos)")
    else:
        status11 = "NO_CUBIERTO"
        miss.append("Incertidumbres y gaps documentados en el expediente")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-11", title=ART45_REQUIREMENTS[10]["title"],
        status=status11, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar data_gaps en impactos y critical_gaps en inventario."],
    ))

    # ── ART45-12: Resumen no técnico ─────────────────────────────────────
    ev = []
    miss = []
    has_rnt = bool(meta.get("non_technical_summary"))
    has_base = bool(
        has_impacts
        and has_measures
        and has_pva
    )

    if has_rnt:
        status12 = "CUBIERTO"
        ev.append("metadata.non_technical_summary presente")
    elif has_base:
        status12 = "PARCIAL"
        ev.append("Material base suficiente: actions + impacts + measures + PVA")
        miss.append("Redaccion del Resumen No Tecnico (Bloque J)")
    else:
        status12 = "NO_CUBIERTO"
        miss.append("Material base para Resumen No Tecnico (impactos + medidas + PVA)")
    items.append(Art45ChecklistItem(
        requirement_id="ART45-12", title=ART45_REQUIREMENTS[11]["title"],
        status=status12, evidence_refs=ev, missing_elements=miss,
        notes=["Verificar Bloque J (resumen no tecnico)."],
    ))

    # ── Generación de issues ─────────────────────────────────────────────
    for item in items:
        if item.status == "NO_CUBIERTO":
            issues.append(Art45ChecklistIssue(
                severity="ERROR",
                code=f"AU01-E{item.requirement_id.split('-')[1]}",
                requirement_id=item.requirement_id,
                message=(
                    f"{item.requirement_id} NO CUBIERTO: {item.title}. "
                    "Elementos faltantes: " + "; ".join(item.missing_elements[:2])
                ),
                recommendation=(
                    "Completar los elementos indicados antes de presentar "
                    "el Documento Ambiental."
                ),
            ))
        elif item.status == "PARCIAL":
            issues.append(Art45ChecklistIssue(
                severity="WARNING",
                code=f"AU01-W{item.requirement_id.split('-')[1]}",
                requirement_id=item.requirement_id,
                message=(
                    f"{item.requirement_id} PARCIAL: {item.title}. "
                    "Falta: " + "; ".join(item.missing_elements[:2])
                ),
                recommendation=(
                    "Completar los elementos indicados o justificar "
                    "por que no son aplicables."
                ),
            ))

    # ── Advertencia de alcance (obligatoria) ─────────────────────────────
    warnings_out: list[str] = [
        "ADVERTENCIA DE ALCANCE: Este checklist es una verificacion estructural "
        "interna. No declara aptitud administrativa ni sustituye revision "
        "tecnica o juridica. La clasificacion final corresponde al organo ambiental."
    ]
    notes_out: list[str] = [
        f"Evaluacion de {len(items)} requisitos del art. 45.1 Ley 21/2013.",
        f"CUBIERTO: {sum(1 for i in items if i.status == 'CUBIERTO')} / "
        f"PARCIAL: {sum(1 for i in items if i.status == 'PARCIAL')} / "
        f"NO_CUBIERTO: {sum(1 for i in items if i.status == 'NO_CUBIERTO')}.",
        "administrative_ready siempre False — AU-01 no declara aptitud administrativa.",
    ]

    return Art45ChecklistResult(
        expediente_id=expediente_id,
        items=items,
        issues=issues,
        administrative_ready=False,
        warnings=warnings_out,
        notes=notes_out,
    )


# ---------------------------------------------------------------------------
# Carga desde archivos del expediente
# ---------------------------------------------------------------------------

def _load_json_safe(path: Path) -> Optional[dict]:
    """Carga un JSON de forma segura; devuelve None si no existe o es inválido."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _find_phase6_model(impactos_dir: Path) -> Optional[dict]:
    """Busca el JSON de Phase6Model más completo disponible."""
    for name in [
        "phase6_model_with_pva.json",
        "phase6_model_with_measures.json",
        "phase6_model_with_conesa.json",
        "phase6_model_with_impacts.json",
    ]:
        data = _load_json_safe(impactos_dir / name)
        if data:
            return data
    return None


def _parse_minimal_phase6(data: dict) -> Phase6Model:
    """Reconstruye un Phase6Model mínimo para el checklist."""
    from eia_agent.core.impact_model import (
        EnvironmentalImpact,
        MitigationMeasure,
        ProjectAction,
        PVAProgram,
        ReceptorFactor,
    )

    actions = [
        ProjectAction(
            action_id=a["action_id"],
            name=a.get("name", ""),
            description=a.get("description", ""),
            action_type=a.get("action_type", "OTRO"),
        )
        for a in data.get("actions", [])
        if "action_id" in a
    ]
    receptor_factors = [
        ReceptorFactor(
            receptor_id=r["receptor_id"],
            inventory_factor_id=r.get("inventory_factor_id", r["receptor_id"].replace("FR-", "FI-")),
            name=r.get("name", r["receptor_id"]),
            notes=r.get("notes", []),
        )
        for r in data.get("receptor_factors", [])
        if "receptor_id" in r
    ]
    impacts = [
        EnvironmentalImpact(
            impact_id=imp["impact_id"],
            action_id=imp.get("action_id", "AC-001"),
            receptor_id=imp.get("receptor_id", "FR-001"),
            name=imp.get("name", ""),
            nature=imp.get("nature", "INDETERMINADO"),
            status=imp.get("status", "PENDIENTE_DATOS"),
            significance_without_measures=imp.get("significance_without_measures", "NO_VALORADO"),
            significance_with_measures=imp.get("significance_with_measures", "NO_VALORADO"),
            data_gaps=imp.get("data_gaps", []),
            measure_ids=imp.get("measure_ids", []),
            pva_ids=imp.get("pva_ids", []),
        )
        for imp in data.get("impacts", [])
        if "impact_id" in imp
    ]
    measures = [
        MitigationMeasure(
            measure_id=m["measure_id"],
            name=m.get("name", ""),
            measure_type=m.get("measure_type", "CORRECTORA"),
            is_diagnostic=m.get("is_diagnostic", False),
            is_prl_only=m.get("is_prl_only", False),
        )
        for m in data.get("measures", [])
        if "measure_id" in m
    ]
    pva_programs = [
        PVAProgram(
            pva_id=p["pva_id"],
            name=p.get("name", ""),
            factor_id=p.get("factor_id", "FI-001"),
            indicator=p.get("indicator", ""),
        )
        for p in data.get("pva_programs", [])
        if "pva_id" in p
    ]
    return Phase6Model(
        expediente_id=data.get("expediente_id", "DESCONOCIDO"),
        actions=actions,
        receptor_factors=receptor_factors,
        impacts=impacts,
        measures=measures,
        pva_programs=pva_programs,
    )


def evaluate_art45_checklist_from_files(
    expediente_path: "str | Path",
) -> Art45ChecklistResult:
    """Evalúa el checklist art.45.1 leyendo los archivos del expediente.

    Busca (sin romper si faltan):
      impactos/phase6_model_with_pva.json (o fallbacks)
      impactos/cumulative_synergistic_result.json
      impactos/pva_coverage_result.json
      inventario/phase5_gate_result.json
      control_interno/phase2_result.json
      control_interno/phase3_result.json
      cartografia/cartografia_plan.json  (o cartography_plan.json)
      clima/phase4_climate_result.json

    Si falta todo: devuelve resultado con NO_CUBIERTO, no lanza excepción
    (salvo si el directorio del expediente no existe).

    Args:
        expediente_path: Ruta al directorio del expediente EIA.

    Raises:
        FileNotFoundError: si el directorio no existe.
    """
    exp_path = Path(expediente_path)
    if not exp_path.exists():
        raise FileNotFoundError(f"Directorio de expediente no encontrado: {exp_path}")

    impactos_dir = exp_path / "impactos"
    inventario_dir = exp_path / "inventario"
    ctrl_dir = exp_path / "control_interno"
    carto_dir = exp_path / "cartografia"
    clima_dir = exp_path / "clima"

    # Modelo Fase 6
    model_data = _find_phase6_model(impactos_dir)
    phase6_model: Optional[Phase6Model] = None
    if model_data:
        try:
            phase6_model = _parse_minimal_phase6(model_data)
        except Exception:
            phase6_model = None

    expediente_id = (
        model_data.get("expediente_id", exp_path.name)
        if model_data else exp_path.name
    )

    # Resultados de módulos anteriores
    cumulative_result = _load_json_safe(impactos_dir / "cumulative_synergistic_result.json")
    pva_coverage_result = _load_json_safe(impactos_dir / "pva_coverage_result.json")
    phase5_gate_result = _load_json_safe(inventario_dir / "phase5_gate_result.json")
    phase2_result = _load_json_safe(ctrl_dir / "phase2_result.json")
    phase3_result = _load_json_safe(ctrl_dir / "phase3_result.json")

    # Cartografía
    carto_plan = (
        _load_json_safe(carto_dir / "cartografia_plan.json")
        or _load_json_safe(carto_dir / "cartography_plan.json")
    )
    mapas = list(carto_dir.glob("*.png")) if carto_dir.exists() else []

    # Metadata compuesta
    metadata: dict = {}
    if phase2_result:
        metadata["object_scope"] = phase2_result.get("object_scope", {})
        if not metadata["object_scope"]:
            metadata["object_scope"] = phase2_result
        metadata["procedure_motivation"] = phase2_result.get("procedure_motivation")
    if phase3_result:
        metadata["phase3_result"] = phase3_result
        if not metadata.get("procedure_motivation"):
            metadata["procedure_motivation"] = phase3_result.get("procedure_text")
    if carto_plan:
        metadata["cartography_plan"] = carto_plan
    if mapas:
        metadata["mapas"] = [str(p) for p in mapas]

    return evaluate_art45_checklist_from_model(
        expediente_id=expediente_id,
        phase6_model=phase6_model,
        phase5_gate_result=phase5_gate_result,
        cumulative_result=cumulative_result,
        pva_coverage_result=pva_coverage_result,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def build_art45_checklist_markdown(result: Art45ChecklistResult) -> str:
    """Genera el informe del checklist art.45.1 en markdown."""
    lines: list[str] = []

    lines.append("# Checklist art. 45 Ley 21/2013 — EIA simplificada")
    lines.append("")
    lines.append(f"**Expediente**: {result.expediente_id}  ")
    lines.append(
        f"**Resultado estructural**: "
        f"{'ESTRUCTURALMENTE COMPLETO' if result.is_structurally_complete() else 'INCOMPLETO'}"
    )
    lines.append("")

    # ── 1. Resumen ──────────────────────────────────────────────────────
    lines.append("## 1. Resumen")
    lines.append("")
    lines.append("| Categoría | Cantidad |")
    lines.append("|-----------|---------|")
    lines.append(f"| CUBIERTO | {result.covered_count()} / 12 |")
    lines.append(f"| PARCIAL | {result.partial_count()} / 12 |")
    lines.append(f"| NO CUBIERTO | {result.not_covered_count()} / 12 |")
    lines.append(f"| ERRORs | {result.error_count()} |")
    lines.append(f"| WARNINGs | {result.warning_count()} |")
    lines.append("")

    # ── 2. Resultado por requisito ───────────────────────────────────────
    lines.append("## 2. Resultado por requisito")
    lines.append("")
    lines.append("| Requisito | Título | Estado | Evidencias | Faltantes |")
    lines.append("|-----------|--------|--------|------------|-----------|")
    for item in result.items:
        ev_str = "; ".join(item.evidence_refs[:2]) or "—"
        miss_str = "; ".join(item.missing_elements[:2]) or "—"
        lines.append(
            f"| {item.requirement_id} | {item.title[:45]} | **{item.status}** "
            f"| {ev_str[:50]} | {miss_str[:50]} |"
        )
    lines.append("")

    # Detalle de cada requisito
    lines.append("## 3. Detalle por requisito")
    lines.append("")
    for item in result.items:
        icon = {"CUBIERTO": "✅", "PARCIAL": "⚠️", "NO_CUBIERTO": "❌", "NO_APLICA": "—"}.get(item.status, "?")
        lines.append(f"### {item.requirement_id} {icon} — {item.title}")
        lines.append("")
        lines.append(f"**Estado**: {item.status}")
        lines.append("")
        if item.evidence_refs:
            lines.append("**Evidencias**:")
            for ev in item.evidence_refs:
                lines.append(f"  - {ev}")
        if item.missing_elements:
            lines.append("**Faltantes**:")
            for ms in item.missing_elements:
                lines.append(f"  - {ms}")
        if item.notes:
            for n in item.notes:
                lines.append(f"> {n}")
        lines.append("")

    # ── 4. Incidencias ──────────────────────────────────────────────────
    lines.append("## 4. Incidencias")
    lines.append("")
    errors = [i for i in result.issues if i.severity == "ERROR"]
    warnings = [i for i in result.issues if i.severity == "WARNING"]
    if errors:
        lines.append("### Errores (requisitos NO CUBIERTOS)")
        lines.append("")
        for issue in errors:
            lines.append(f"**[{issue.code}]** {issue.message}")
            lines.append(f"> _Recomendación_: {issue.recommendation}")
            lines.append("")
    if warnings:
        lines.append("### Advertencias (requisitos PARCIALES)")
        lines.append("")
        for issue in warnings:
            lines.append(f"**[{issue.code}]** {issue.message}")
            lines.append(f"> _Recomendación_: {issue.recommendation}")
            lines.append("")
    if not errors and not warnings:
        lines.append("_Sin incidencias detectadas._")
        lines.append("")

    # ── 5. Advertencia de alcance (obligatoria) ──────────────────────────
    lines.append("## 5. Advertencia de alcance")
    lines.append("")
    lines.append(
        "> **Este checklist es una verificación estructural interna. "
        "No declara aptitud administrativa ni sustituye revisión técnica "
        "o jurídica. No revisa la legislación autonómica específica "
        "(BOC, normativa de Canarias u otras CCAA). "
        "La clasificación final del expediente corresponde al órgano ambiental "
        "mediante el Informe de Impacto Ambiental (art. 47 Ley 21/2013).**"
    )
    lines.append("")
    lines.append(
        f"> `administrative_ready` = {result.administrative_ready} "
        "— AU-01 nunca declara aptitud administrativa."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Escritura de outputs
# ---------------------------------------------------------------------------

def write_art45_checklist_outputs(
    result: Art45ChecklistResult,
    output_dir: "str | Path",
) -> tuple[Path, Path]:
    """Escribe los outputs del checklist art.45.

    Escribe:
      - {output_dir}/art45_checklist_result.json
      - {output_dir}/art45_checklist_result.md

    Returns:
        Tupla (path_json, path_md).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "art45_checklist_result.json"
    md_path = output_dir / "art45_checklist_result.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_art45_checklist_markdown(result))

    return json_path, md_path
