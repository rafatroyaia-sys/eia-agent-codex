"""
inventory_heritage_builder -- IV-09
Constructor de factor FI-012 Patrimonio cultural desde Fase 2/Fase 4 offline.

Integra la informacion de actividad de Fase 2 y el plan cartografico de Fase 4
para construir FI-012 Patrimonio cultural con:
  - deteccion de menciones patrimoniales en la documentacion disponible;
  - gaps de consulta oficial al organo/inventario patrimonial competente;
  - caracterizacion prudente de gabinete con los datos existentes.

Reglas de prudencia (no negociables):
  - No se afirma "no hay patrimonio", "sin yacimientos" ni "sin afeccion patrimonial".
  - No se descarta afeccion patrimonial sin consulta a inventario oficial.
  - No se sustituye la consulta al organo autonómico/municipal competente.
  - ready_for_impact_assessment: False por defecto en modo offline.
  - inventory_semaphore: nunca VERDE sin consulta oficial documentada.
  - No se usan terminos de valoracion de impacto: COMPATIBLE, MODERADO, SEVERO, CRITICO.

No consulta inventarios patrimoniales.
No consulta BIC ni catalogos oficiales.
No verifica patrimonio in situ.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) -- FactorInventory, InventoryGap, InventorySummary
  F4-01 (phase4_offline_pipeline) -- estructura phase4_result.json
  OB-06 (phase2_pipeline) -- estructura phase2_result.json (opcional)
  CA-10 (cartography_plan) -- cartography_plan.json (opcional)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_inventory_summary,
)

# ---------------------------------------------------------------------------
# Terminos de deteccion
# ---------------------------------------------------------------------------

_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "patrimonio",
    "arqueolog",
    "yacimiento",
    "bien de inter",
    "bic",
    "catalog",
    "inventario patrimonial",
    "proteccion cultural",
    "protección cultural",
    "historic",
    "etnografi",
    "igpc",
    "pgou",
    "planeamiento",
    "rupestre",
    "resto arqueolog",
    "zona arqueolog",
)

_DETECTION_TERMS: tuple[str, ...] = (
    "patrimonio",
    "arqueolog",
    "yacimiento",
    "bic",
    "bien de interes cultural",
    "bien de interés cultural",
    "catalog",
    "historic",
    "etnografi",
    "igpc",
    "proteccion cultural",
    "protección cultural",
    "rupestre",
    "resto arqueolog",
    "zona arqueolog",
)


# ---------------------------------------------------------------------------
# Funciones auxiliares privadas
# ---------------------------------------------------------------------------


def _has_location(
    phase2_data: dict | None,
    phase4_result: dict | None,
) -> bool:
    """Detecta si hay ubicacion o coordenadas disponibles en los datos."""
    if phase2_data:
        scope = phase2_data.get("object_scope") or {}
        coords = scope.get("coordenadas_wgs84")
        if coords:
            return True
    if phase4_result:
        cart = phase4_result.get("cartography_plan") or {}
        center = cart.get("center") or {}
        if center.get("lat") is not None:
            return True
        clim = phase4_result.get("climate") or {}
        station = clim.get("selected_station") or {}
        if station.get("station_id"):
            return True
    return False


def _extract_phase2_activity_text(phase2_data: dict | None) -> str:
    """Extrae texto de actividad y operaciones de phase2_data en minusculas."""
    if not phase2_data:
        return ""
    scope = phase2_data.get("object_scope") or {}
    parts: list[str] = []
    ops = scope.get("operaciones_incluidas") or []
    if isinstance(ops, list):
        parts.extend(str(op) for op in ops if op)
    elif isinstance(ops, str) and ops:
        parts.append(ops)
    for key in ("descripcion_actividad", "actividad", "denominacion", "nombre_proyecto", "notas"):
        val = scope.get(key)
        if val:
            parts.append(str(val))
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Funciones publicas auxiliares
# ---------------------------------------------------------------------------


def extract_heritage_context(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> str:
    """Extrae texto relacionado con patrimonio cultural de los datos disponibles.

    Recorre de forma segura dicts y listas buscando menciones a:
    patrimonio, arqueologia, yacimiento, BIC, catalogo, historico,
    etnografico, IGPC, PGOU, planeamiento, proteccion cultural, etc.

    Devuelve str en minusculas con el contenido relevante encontrado.
    """
    parts: list[str] = []

    def _scrape(obj: object, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(obj, str):
            lo = obj.lower()
            if any(kw in lo for kw in _CONTEXT_KEYWORDS):
                parts.append(lo)
        elif isinstance(obj, dict):
            for v in obj.values():
                _scrape(v, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _scrape(item, depth + 1)

    _scrape(phase2_data)
    _scrape(phase4_result)
    _scrape(cartography_plan)

    return " ".join(parts)


def detect_heritage_mentions(text: str) -> list[str]:
    """Detecta terminos de patrimonio cultural en texto disponible.

    Devuelve lista de terminos encontrados (sin duplicados, en orden de aparicion).
    No interpreta mas alla de presencia textual.
    """
    found: list[str] = []
    lo = text.lower()
    for term in _DETECTION_TERMS:
        if term in lo and term not in found:
            found.append(term)
    return found


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class HeritageInventoryBuildResult:
    """Resultado de IV-09: FI-012 Patrimonio cultural."""

    factor: FactorInventory
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "factor": self.factor.to_dict(),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        f = self.factor
        lines = [
            "HeritageInventoryBuildResult:",
            f"  {f.factor_id} {f.factor_name}: "
            f"evidence={f.evidence_status} "
            f"field_mode={f.field_mode} "
            f"semaphore={f.inventory_semaphore} "
            f"gaps={len(f.gaps)}",
        ]
        if self.warnings:
            lines.append(f"  warnings: {self.warnings}")
        if self.notes:
            lines.append(f"  notes: {self.notes}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Constructor FI-012 Patrimonio cultural
# ---------------------------------------------------------------------------


def build_heritage_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-012 Patrimonio cultural desde datos de Fase 2 y Fase 4.

    Fuentes usadas:
      - phase2_data.object_scope: descripcion de actividad y operaciones.
      - phase4_result: plan cartografico y datos de ubicacion.
      - cartography_plan: plan cartografico explícito.

    Logica de evidencia:
      - DECLARADO si la documentacion del promotor contiene informacion
        patrimonial concreta (menciones a BIC, yacimiento, arqueologia, etc.).
      - ESTIMADO si hay ubicacion/coordenadas o menciones patrimoniales en
        datos de fase4/cartografia.
      - PENDIENTE si no hay informacion minima de ubicacion ni menciones.

    Logica de semaforo:
      - ROJO_AMARILLO si hay menciones patrimoniales explícitas sin resolver.
      - AMARILLO si hay ubicacion/coordenadas sin menciones patrimoniales.
      - NO_CONSTA si no hay informacion.
      - Nunca VERDE sin consulta oficial documentada.

    Logica de field_mode:
      - CAMPO_RECOMENDADO si hay ubicacion.
      - NO_CONSTA si sin ubicacion.

    GAP-FI-012-001: consulta oficial al organo/inventario patrimonial competente.
      ALTA / GABINETE. Siempre presente.
    GAP-FI-012-002: aclaracion de mencion patrimonial detectada.
      ALTA / GABINETE. Solo si hay menciones patrimoniales.
    ready_for_impact_assessment: False por defecto.
    """
    fid = "FI-012"
    fname = FACTOR_NAMES.get(fid, "Patrimonio cultural")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_loc = _has_location(phase2_data, phase4_result)
    if not has_loc and effective_plan:
        center = (effective_plan.get("center") or {})
        if center.get("lat") is not None:
            has_loc = True

    activity_text = _extract_phase2_activity_text(phase2_data)
    all_context = extract_heritage_context(phase2_data, phase4_result, effective_plan)

    activity_heritage_mentions = detect_heritage_mentions(activity_text)
    all_heritage_mentions = detect_heritage_mentions(all_context)

    has_promoter_declaration = bool(activity_heritage_mentions)
    has_any_mention = bool(all_heritage_mentions)

    # --- Evidence status ---
    if has_promoter_declaration:
        evidence_status = "DECLARADO"
    elif has_loc or has_any_mention:
        evidence_status = "ESTIMADO"
    else:
        evidence_status = "PENDIENTE"

    # --- Field mode ---
    if has_loc:
        field_mode = "CAMPO_RECOMENDADO"
    else:
        field_mode = "NO_CONSTA"

    # --- Semaphore ---
    if evidence_status == "PENDIENTE":
        inventory_semaphore = "NO_CONSTA"
    elif has_any_mention:
        inventory_semaphore = "ROJO_AMARILLO"
    elif has_loc:
        inventory_semaphore = "AMARILLO"
    else:
        inventory_semaphore = "NO_CONSTA"

    # --- Data sources ---
    data_sources: list[str] = []
    if phase2_data:
        data_sources.append("OB-06 — documentacion del promotor (Fase 2)")
    if phase4_result or effective_plan:
        data_sources.append("F4-01 — plan de Fase 4 offline")

    # --- Description ---
    desc_parts: list[str] = []

    desc_parts.append(
        "Caracterizacion preliminar de gabinete de FI-012 Patrimonio cultural. "
        "No se ha realizado consulta al inventario patrimonial autonómico, "
        "municipal ni al organo competente en materia de patrimonio cultural."
    )

    if has_loc:
        desc_parts.append(
            "Se dispone de referencia de ubicacion del proyecto. "
            "La consulta a los instrumentos de planeamiento (PGOU, Plan General, "
            "catalogo municipal de proteccion) y al inventario patrimonial autonómico "
            "es necesaria para determinar la presencia de bienes catalogados o "
            "yacimientos en el ambito del proyecto o su entorno."
        )
    else:
        desc_parts.append(
            "No se dispone de coordenadas ni referencia de ubicacion suficiente "
            "para situar el proyecto en relacion con los inventarios patrimoniales. "
            "La ubicacion es indispensable antes de cualquier consulta patrimonial."
        )

    if has_any_mention:
        terms_str = ", ".join(all_heritage_mentions[:6])
        if len(all_heritage_mentions) > 6:
            terms_str += "..."
        desc_parts.append(
            f"Se detectan menciones relacionadas con patrimonio cultural en la "
            f"documentacion disponible: {terms_str}. "
            "Estas menciones no constituyen caracterizacion del patrimonio presente "
            "y requieren consulta y aclaracion con el organo patrimonial competente "
            "antes de la redaccion del Documento Ambiental."
        )

    desc_parts.append(
        "No es posible descartar la existencia de afeccion a bienes culturales, "
        "arqueologicos o etnograficos en el ambito del proyecto "
        "sin consulta al organo autonómico y/o municipal competente. "
        "Esta caracterizacion es de caracter preliminar y no sustituye "
        "la consulta oficial al inventario patrimonial."
    )

    description = " ".join(desc_parts)

    # --- Gaps ---
    gap_official = InventoryGap(
        gap_id="GAP-FI-012-001",
        factor_id="FI-012",
        field="consulta_inventario_patrimonial_oficial",
        description=(
            "Pendiente consulta al inventario patrimonial autonómico "
            "(p.ej. IGPC en Canarias, IAPH en Andalucía u organo equivalente) "
            "y al catalogo municipal de bienes protegidos (PGOU u instrumento "
            "de planeamiento vigente) para determinar la presencia de bienes "
            "de interes cultural (BIC), yacimientos arqueologicos, bienes "
            "etnograficos o cualquier otro bien catalogado en el ambito del "
            "proyecto y su entorno de afeccion. "
            "Sin esta consulta no puede completarse FI-012 ni iniciarse la "
            "valoracion de impactos sobre el patrimonio cultural."
        ),
        criticality="ALTA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    gaps = [gap_official]

    if has_any_mention:
        terms_gap = ", ".join(all_heritage_mentions[:4])
        gap_clarification = InventoryGap(
            gap_id="GAP-FI-012-002",
            factor_id="FI-012",
            field="aclaracion_menciones_patrimoniales_detectadas",
            description=(
                f"Se han detectado en la documentacion disponible menciones "
                f"a: {terms_gap}. "
                "Es necesario aclarar el origen y alcance de estas menciones "
                "mediante consulta directa al organo patrimonial competente "
                "y/o al promotor, antes de determinar si existe afeccion real "
                "a bienes culturales en el ambito del proyecto."
            ),
            criticality="ALTA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        )
        gaps.append(gap_clarification)

    return FactorInventory(
        factor_id=fid,
        factor_name=fname,
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=inventory_semaphore,
        description=description,
        data_sources=data_sources,
        gaps=gaps,
        ready_for_impact_assessment=False,
    )


# ---------------------------------------------------------------------------
# Constructor con resultado
# ---------------------------------------------------------------------------


def build_heritage_inventory_factor_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> HeritageInventoryBuildResult:
    """Construye FI-012 y lo devuelve como HeritageInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    fi012 = build_heritage_factor_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_plan,
    )

    if fi012.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-012 Patrimonio cultural: sin ubicacion ni documentacion del promotor. "
            "No es posible caracterizar el factor patrimonial. "
            "Pendiente coordenadas y consulta oficial."
        )

    if fi012.inventory_semaphore == "ROJO_AMARILLO":
        warnings.append(
            "FI-012 Patrimonio cultural: menciones patrimoniales detectadas en la "
            "documentacion sin resolver. Consulta al organo patrimonial urgente "
            "antes de continuar con el inventario."
        )

    notes.append(
        f"IV-09: FI-012={fi012.evidence_status}/{fi012.inventory_semaphore}. "
        f"Menciones patrimoniales: {len(fi012.gaps) > 1}. "
        "Consulta oficial pendiente."
    )

    return HeritageInventoryBuildResult(
        factor=fi012,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_heritage_factor_into_summary(
    summary: InventorySummary,
    factor: FactorInventory,
) -> InventorySummary:
    """Sustituye FI-012 en un InventorySummary sin mutar el original.

    Preserva el orden canonico de FACTOR_NAMES.
    Propaga warnings y notes del summary original.
    """
    merged_map = {f.factor_id: f for f in summary.factors}
    merged_map[factor.factor_id] = factor

    merged_factors = [merged_map[fid] for fid in sorted(FACTOR_NAMES.keys()) if fid in merged_map]

    new_summary = build_inventory_summary(summary.expediente_id, merged_factors)
    new_summary.warnings = list(summary.warnings)
    new_summary.notes = list(summary.notes)
    return new_summary
