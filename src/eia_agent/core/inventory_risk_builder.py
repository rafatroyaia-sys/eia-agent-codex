"""
inventory_risk_builder -- IV-03
Constructor de factores FI-005 Inundabilidad y FI-016 Riesgos naturales
desde Fase 4 offline.

Lee los outputs de Fase 4 (phase4_result.json, cartography_plan.json)
y construye los factores FI-005 e FI-016 con estado ESTIMADO/PENDIENTE
y semaforo AMARILLO/NO_CONSTA segun la informacion disponible.

Regla de prudencia aplicada:
  - Ninguna descripcion afirma "sin riesgo", "riesgo nulo" ni cierra
    ningun riesgo como inexistente.
  - La verificacion con fuentes oficiales siempre queda pendiente (GAP ALTA).
  - ready_for_impact_assessment: False siempre en modo offline.
  - inventory_semaphore: nunca VERDE en modo offline.

No consulta SNCZI.
No consulta WMS ni WMTS.
No verifica riesgo real.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
- IV-00: inventory_model.py
- F4-01: phase4_offline_pipeline.py (outputs JSON)
- CA-10: cartography_plan.py (outputs JSON)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_inventory_summary,
)


# ---------------------------------------------------------------------------
# Auxiliares internos
# ---------------------------------------------------------------------------

def _find_inundabilidad_map(maps: list[dict]) -> dict | None:
    """Devuelve el primer MapSpec dict que corresponde a inundabilidad, o None.

    Detecta MAP-006 (map_type=inundabilidad_riesgos) o cualquier mapa
    cuyo title/purpose/required_layers contenga la raiz 'inundab'.
    """
    for m in maps:
        if m.get("map_type") == "inundabilidad_riesgos":
            return m
        combined = (
            m.get("title", "")
            + " "
            + m.get("purpose", "")
            + " "
            + " ".join(m.get("required_layers", []))
        ).lower()
        if "inundab" in combined:
            return m
    return None


def _extract_center(cartography_plan: dict) -> dict | None:
    """Extrae el dict center del plan cartografico, o None si no existe o no tiene lat."""
    if not cartography_plan:
        return None
    center = cartography_plan.get("center")
    if not center or not center.get("lat"):
        return None
    return center


def _has_coordinates(
    phase4_result: dict,
    cartography_plan: dict | None,
) -> bool:
    """Devuelve True si hay coordenadas del emplazamiento disponibles en Fase 4.

    Comprueba en orden:
    1. Plan cartografico externo (argumento).
    2. Plan cartografico embebido en phase4_result.
    3. Estacion climatica seleccionada (las coordenadas del expediente se usaron
       para seleccionarla, por lo que estan disponibles).
    """
    if cartography_plan and _extract_center(cartography_plan):
        return True
    embedded = phase4_result.get("cartography_plan")
    if embedded and _extract_center(embedded):
        return True
    climate = phase4_result.get("climate")
    if climate and climate.get("selected_station"):
        return True
    return False


# ---------------------------------------------------------------------------
# RiskInventoryBuildResult
# ---------------------------------------------------------------------------

@dataclass
class RiskInventoryBuildResult:
    """Resultado del constructor de factores de riesgo desde Fase 4 offline (IV-03)."""

    factors: list[FactorInventory] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "factors": [
                {
                    "factor_id": f.factor_id,
                    "factor_name": FACTOR_NAMES.get(f.factor_id, f.factor_id),
                    "evidence_status": f.evidence_status,
                    "field_mode": f.field_mode,
                    "inventory_semaphore": f.inventory_semaphore,
                    "ready_for_impact_assessment": f.ready_for_impact_assessment,
                    "gap_count": len(f.gaps),
                }
                for f in self.factors
            ],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [f"Factores de riesgo IV-03 -- {len(self.factors)} factor(es)"]
        for f in self.factors:
            factor_name = FACTOR_NAMES.get(f.factor_id, f.factor_id)
            lines.append(
                f"  {f.factor_id} {factor_name}: "
                f"{f.inventory_semaphore} / {f.evidence_status} / "
                f"ready={f.ready_for_impact_assessment}"
            )
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  NOTA: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_flood_risk_factor_from_phase4
# ---------------------------------------------------------------------------

def build_flood_risk_factor_from_phase4(
    phase4_result: dict,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-005 Inundabilidad desde los outputs de Fase 4 offline.

    Reglas de prudencia:
    - inventory_semaphore nunca es VERDE en modo offline.
    - ready_for_impact_assessment siempre False.
    - Gap GAP-FI-005-001 siempre presente (verificacion oficial pendiente).
    - No se afirma que no existe riesgo ni que el riesgo es nulo.

    Args:
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (obligatorio).
        cartography_plan: Dict de CartographyPlanResult.to_dict() (opcional;
                          si None se usa cartography_plan embebido en phase4_result).

    Returns:
        FactorInventory para FI-005 Inundabilidad con semaforo AMARILLO o NO_CONSTA.
    """
    # Resolver plan efectivo
    effective_plan = cartography_plan
    if effective_plan is None:
        effective_plan = phase4_result.get("cartography_plan")

    maps: list[dict] = effective_plan.get("maps", []) if effective_plan else []
    inund_map = _find_inundabilidad_map(maps)
    has_plan = bool(effective_plan)
    has_inund_map = inund_map is not None

    warnings: list[str] = []
    notes: list[str] = []

    # --- Nivel de evidencia ---
    if has_inund_map:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "AMARILLO"
    elif has_plan:
        evidence_status = "PENDIENTE"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "NO_CONSTA"
        warnings.append(
            "El plan cartografico de Fase 4 no incluye mapa especifico de inundabilidad. "
            "FI-005 no puede calificarse hasta incorporar fuentes oficiales (SNCZI, RIESGOMAP)."
        )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        semaphore = "NO_CONSTA"
        warnings.append(
            "No se dispone de plan cartografico de Fase 4. "
            "FI-005 Inundabilidad no puede evaluarse en modo offline."
        )

    # --- Description ---
    parts: list[str] = [
        "Inundabilidad evaluada en modo offline a partir de los outputs de Fase 4 (F4-01)."
    ]
    if has_inund_map:
        map_status = inund_map.get("status", "PLANNED")
        map_id = inund_map.get("map_id", "MAP-006")
        map_title = inund_map.get("title", "Inundabilidad / riesgos fisicos")
        map_file = inund_map.get("output_filename", "MAP-006_inundabilidad_riesgos.png")
        parts.append(
            f"El plan cartografico incluye el mapa '{map_title}' "
            f"({map_id}, estado: {map_status}, salida: {map_file}). "
            "La fuente es cartografia esquematica offline de caracter provisional, "
            "sin datos reales de inundabilidad."
        )
        srcs = inund_map.get("source_candidates", [])
        if srcs:
            srcs_str = ", ".join(srcs[:2])
            parts.append(f"Fuentes oficiales candidatas para verificacion: {srcs_str}.")
    elif has_plan:
        parts.append(
            "El plan cartografico offline no incluye cobertura especifica de inundabilidad. "
            "No se dispone de estimacion provisional para este factor."
        )
    else:
        parts.append(
            "No se dispone de plan cartografico offline. "
            "No es posible generar ninguna estimacion provisional de inundabilidad."
        )

    parts.append(
        "La inundabilidad debe verificarse con fuentes oficiales antes del DA definitivo: "
        "SNCZI (Sistema Nacional de Cartografia de Zonas Inundables del MITERD), "
        "RIESGOMAP (Canarias), u organismo competente de la CCAA. "
        "La cartografia esquematica offline no sustituye la consulta oficial "
        "y no permite confirmar ni excluir la presencia de zonas inundables."
    )

    description = " ".join(parts)

    # --- Data sources ---
    data_sources: list[str] = ["F4-01 -- Pipeline Fase 4 offline"]
    if has_plan:
        data_sources.append("CA-10 -- Plan cartografico offline")
    if has_inund_map:
        map_id_str = inund_map.get("map_id", "MAP-006")
        map_status_str = inund_map.get("status", "PLANNED")
        data_sources.append(
            f"CA-11 -- Mapa esquematico '{map_id_str}' "
            f"[{map_status_str}] (provisional, no oficial, sin datos reales)"
        )
    data_sources.append(
        "Fuente oficial pendiente: SNCZI / RIESGOMAP / organismo autonómico competente"
    )

    # --- Notes ---
    notes.append(
        "FI-005 Inundabilidad: verificacion obligatoria con SNCZI o equivalente autonómico "
        "antes de valorar impactos relacionados con inundabilidad. "
        "La cartografia offline es provisional y no apta para el DA definitivo."
    )

    # --- Justificaciones ---
    if has_inund_map:
        field_mode_just = (
            "La evaluacion de inundabilidad requiere comprobacion con fuente oficial "
            "(SNCZI, RIESGOMAP) para confirmar o excluir zonas inundables en el emplazamiento. "
            "Se recomienda el modo campo o consulta directa antes de la valoracion de impactos."
        )
        sem_just = (
            "Semaforo AMARILLO: existe mapa previsto de inundabilidad en el plan cartografico "
            "offline (CA-10/CA-11), pero la fuente es provisional y no oficial. "
            "No puede calificarse VERDE sin verificacion con SNCZI o equivalente autonómico."
        )
    elif has_plan:
        field_mode_just = (
            "El plan cartografico offline no incluye mapa de inundabilidad. "
            "Se recomienda consulta directa de fuentes oficiales para resolver el gap."
        )
        sem_just = ""
    else:
        field_mode_just = ""
        sem_just = ""

    # --- Gap obligatorio GAP-FI-005-001 ---
    gap = InventoryGap(
        gap_id="GAP-FI-005-001",
        factor_id="FI-005",
        field="cartografia_inundabilidad_oficial",
        description=(
            "No se ha verificado la inundabilidad con fuentes oficiales "
            "(SNCZI, RIESGOMAP u organismo autonómico competente). "
            "La cartografia esquematica offline es provisional y no apta para el DA definitivo. "
            "Requiere consulta oficial antes de la valoracion de impactos relacionados "
            "con inundabilidad. La presencia o ausencia de zonas inundables "
            "no puede confirmarse con los datos de Fase 4 offline."
        ),
        criticality="ALTA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    return FactorInventory(
        factor_id="FI-005",
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=semaphore,
        description=description,
        data_sources=data_sources,
        gaps=[gap],
        ready_for_impact_assessment=False,
        warnings=warnings,
        notes=notes,
        field_mode_justification=field_mode_just,
        semaphore_justification=sem_just,
    )


# ---------------------------------------------------------------------------
# build_natural_risks_factor_from_phase4
# ---------------------------------------------------------------------------

def build_natural_risks_factor_from_phase4(
    phase4_result: dict,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-016 Riesgos naturales desde los outputs de Fase 4 offline.

    Reglas de prudencia:
    - No cierra ningun riesgo como inexistente ni como fuera del ambito.
    - No afirma que no existe riesgo.
    - inventory_semaphore nunca VERDE en modo offline.
    - ready_for_impact_assessment siempre False.
    - Gap GAP-FI-016-001 siempre presente.

    Los riesgos minimos a verificar son:
      (1) Inundabilidad — SNCZI/RIESGOMAP;
      (2) Incendio forestal — si procede por clasificacion forestal;
      (3) Sismicidad — NCSE-02;
      (4) Episodios meteorologicos extremos — AEMET;
      (5) Riesgo volcanico — si el ambito territorial lo requiere.

    Args:
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (obligatorio).
        cartography_plan: Dict de CartographyPlanResult.to_dict() (opcional).

    Returns:
        FactorInventory para FI-016 Riesgos naturales con semaforo AMARILLO o NO_CONSTA.
    """
    # Resolver plan efectivo
    effective_plan = cartography_plan
    if effective_plan is None:
        effective_plan = phase4_result.get("cartography_plan")

    has_plan = bool(effective_plan)
    has_coords = _has_coordinates(phase4_result, cartography_plan)

    warnings: list[str] = []
    notes: list[str] = []

    # --- Nivel de evidencia ---
    if has_coords and has_plan:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "AMARILLO"
    elif has_coords:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "NO_CONSTA"
        warnings.append(
            "No se dispone de plan cartografico de Fase 4. "
            "La evaluacion de riesgos naturales queda en estado preliminar."
        )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        semaphore = "NO_CONSTA"
        warnings.append(
            "No se dispone de coordenadas verificadas ni plan cartografico. "
            "FI-016 Riesgos naturales no puede evaluarse en modo offline."
        )

    # --- Description ---
    parts: list[str] = [
        "Riesgos naturales evaluados en modo offline a partir de los outputs de Fase 4 (F4-01). "
        "La evaluacion offline permite preparar el analisis de riesgos "
        "y planificar la consulta de fuentes oficiales, "
        "pero no sustituye la consulta a los organismos competentes."
    ]
    parts.append(
        "Deben verificarse, como minimo, los siguientes riesgos antes del DA definitivo: "
        "(1) inundabilidad -- ver FI-005 y SNCZI/RIESGOMAP; "
        "(2) incendio forestal -- si la ubicacion lo requiere segun clasificacion forestal; "
        "(3) sismicidad -- segun zonificacion sismica nacional (NCSE-02); "
        "(4) episodios meteorologicos extremos -- segun datos AEMET y catalogo de riesgos; "
        "(5) riesgo volcanico -- si el ambito territorial es archipielago canario "
        "u otra zona con actividad volcanica potencial."
    )
    if has_coords and has_plan:
        parts.append(
            "Se dispone de coordenadas del emplazamiento y plan cartografico offline (CA-10). "
            "Esta informacion permite planificar la consulta georeferenciada "
            "de fuentes oficiales de riesgos naturales."
        )
    elif has_coords:
        parts.append(
            "Se dispone de coordenadas del emplazamiento. "
            "No se ha generado plan cartografico especifico para riesgos naturales en Fase 4."
        )
    else:
        parts.append(
            "No se dispone de coordenadas verificadas. "
            "No es posible realizar ninguna estimacion previa de riesgos naturales."
        )
    parts.append(
        "Ningun riesgo natural puede confirmarse como inexistente ni excluirse del analisis "
        "con los datos de Fase 4 offline. "
        "La calificacion definitiva requiere consulta de fuentes oficiales."
    )

    description = " ".join(parts)

    # --- Data sources ---
    data_sources: list[str] = ["F4-01 -- Pipeline Fase 4 offline"]
    if has_plan:
        data_sources.append("CA-10 -- Plan cartografico offline")
    data_sources.append(
        "Fuentes oficiales pendientes: SNCZI, IGME Riesgos Geologicos, "
        "AEMET Catalogo de riesgos, RIESGOMAP (Canarias), NCSE-02"
    )

    # --- Notes ---
    notes.append(
        "FI-016 Riesgos naturales: ninguno de los riesgos enumerados puede "
        "confirmarse como inexistente con datos offline. "
        "Verificacion oficial obligatoria antes de la valoracion de impactos."
    )
    if has_coords:
        notes.append(
            "Coordenadas disponibles en Fase 4. "
            "Usar para consulta georeferenciada de fuentes oficiales de riesgos."
        )

    # --- Justificaciones ---
    if has_coords and has_plan:
        field_mode_just = (
            "La evaluacion de riesgos naturales requiere consulta de fuentes oficiales "
            "georeferenciadas para el emplazamiento del expediente. "
            "Se recomienda el modo campo complementario para riesgos sin cartografia oficial."
        )
        sem_just = (
            "Semaforo AMARILLO: se dispone de coordenadas y plan cartografico offline "
            "que permiten preparar la consulta de fuentes oficiales de riesgos naturales. "
            "No puede calificarse VERDE sin verificacion oficial de cada tipo de riesgo."
        )
    elif has_coords:
        field_mode_just = (
            "Coordenadas disponibles pero sin plan cartografico especifico. "
            "Se recomienda consulta directa de organismos de riesgos naturales."
        )
        sem_just = ""
    else:
        field_mode_just = ""
        sem_just = ""

    # --- Gap obligatorio GAP-FI-016-001 ---
    gap = InventoryGap(
        gap_id="GAP-FI-016-001",
        factor_id="FI-016",
        field="verificacion_riesgos_naturales_oficial",
        description=(
            "No se ha verificado ningun riesgo natural con fuentes oficiales. "
            "Pendiente consulta de: SNCZI (inundabilidad), IGME (riesgos geologicos), "
            "AEMET (episodios meteorologicos extremos), "
            "organismos autonómicos (riesgo volcanico si aplica). "
            "La calificacion de cada riesgo como presente, bajo o relevante "
            "no puede realizarse con los datos de Fase 4 offline."
        ),
        criticality="ALTA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    return FactorInventory(
        factor_id="FI-016",
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=semaphore,
        description=description,
        data_sources=data_sources,
        gaps=[gap],
        ready_for_impact_assessment=False,
        warnings=warnings,
        notes=notes,
        field_mode_justification=field_mode_just,
        semaphore_justification=sem_just,
    )


# ---------------------------------------------------------------------------
# build_risk_inventory_factors_from_phase4
# ---------------------------------------------------------------------------

def build_risk_inventory_factors_from_phase4(
    phase4_result: dict,
    cartography_plan: dict | None = None,
) -> RiskInventoryBuildResult:
    """Construye FI-005 e FI-016 desde los outputs de Fase 4 offline.

    Args:
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (obligatorio).
        cartography_plan: Dict de CartographyPlanResult.to_dict() (opcional;
                          si None se usa el embebido en phase4_result).

    Returns:
        RiskInventoryBuildResult con [FI-005, FI-016], warnings y notes.
    """
    warnings: list[str] = []
    notes: list[str] = []

    fi005 = build_flood_risk_factor_from_phase4(phase4_result, cartography_plan)
    fi016 = build_natural_risks_factor_from_phase4(phase4_result, cartography_plan)

    # Aviso si no hay ningun dato de Fase 4 de cartografia
    effective = cartography_plan or phase4_result.get("cartography_plan")
    if not effective:
        warnings.append(
            "No se dispone de plan cartografico en Fase 4. "
            "FI-005 e FI-016 quedan en estado PENDIENTE/NO_CONSTA. "
            "Ejecutar CA-10 y F4-01 para enriquecer estos factores."
        )

    notes.append(
        "Factores de riesgo FI-005 e FI-016 construidos en modo offline (IV-03). "
        "Ambos quedan con gap de criticidad ALTA y ready_for_impact_assessment=False "
        "hasta verificacion con fuentes oficiales."
    )

    return RiskInventoryBuildResult(
        factors=[fi005, fi016],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# merge_risk_factors_into_summary
# ---------------------------------------------------------------------------

def merge_risk_factors_into_summary(
    summary: InventorySummary,
    risk_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-005 y FI-016 en un InventorySummary existente.

    No muta el summary original. Crea un nuevo InventorySummary con los
    factores de riesgo reemplazados. Conserva el orden canonico de factores
    y propaga los warnings/notes del summary original.

    Args:
        summary:      InventorySummary original (no se muta).
        risk_factors: Lista de FactorInventory a sustituir (FI-005, FI-016 o ambos).

    Returns:
        Nuevo InventorySummary con 16 factores (sin duplicados).
    """
    risk_ids = {f.factor_id for f in risk_factors}

    # Construir lista de factores preservando el orden canonico
    new_factors: list[FactorInventory] = []
    for existing in summary.factors:
        if existing.factor_id in risk_ids:
            replacement = next(f for f in risk_factors if f.factor_id == existing.factor_id)
            new_factors.append(replacement)
        else:
            new_factors.append(existing)

    new_summary = build_inventory_summary(summary.expediente_id, new_factors)

    # Propagar warnings y notes del summary original
    new_summary.warnings.extend(summary.warnings)
    new_summary.notes.extend(summary.notes)

    return new_summary
