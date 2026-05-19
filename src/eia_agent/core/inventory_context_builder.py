"""
inventory_context_builder -- IV-04
Constructor de factores FI-011 Paisaje y FI-013 Socioeconomia
desde Fase 2/Fase 4 offline.

Lee los outputs de Fase 2 (phase2_result.json / object_scope) y Fase 4
(phase4_result.json, cartografia_plan.json) y construye los factores
FI-011 e FI-013 con estado ESTIMADO/DECLARADO/PENDIENTE y semaforo
AMARILLO/NO_CONSTA segun la informacion disponible.

Reglas de prudencia aplicadas:
  - FI-011: no se afirma calidad paisajistica, fragilidad ni magnitud de
    alteracion visual. Nunca VERDE. ready_for_impact_assessment siempre False.
  - FI-013: no se afirma generacion de empleo salvo que conste. No se
    cuantifican efectos socioeconomicos. No se usan factores socioeconomicos
    para anular la valoracion de impactos ambientales.
  - Ninguna descripcion contiene "sin afecion", "sin impacto", "inexistente",
    "beneficio economico neto" ni la palabra "compensa".

No consulta visores de paisaje.
No consulta planeamiento urbanistico.
No consulta WMS ni WMTS.
No verifica compatibilidad urbanistica real.
No cuantifica empleo ni renta.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
- IV-00: inventory_model.py
- OB-06: phase2_pipeline.py (outputs JSON)
- F4-01: phase4_offline_pipeline.py (outputs JSON)
- CA-10: cartography_plan.py (outputs JSON)
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
# Auxiliares internos
# ---------------------------------------------------------------------------

def _extract_object_scope(phase2_data: dict | None) -> dict:
    """Devuelve el dict object_scope de un phase2_result, o {} si no existe."""
    if not phase2_data:
        return {}
    return phase2_data.get("object_scope") or {}


def _has_location(
    phase2_data: dict | None,
    phase4_result: dict | None,
) -> bool:
    """True si hay coordenadas del emplazamiento disponibles.

    Comprueba en orden:
    1. Object scope Fase 2 (coordenadas_wgs84 no vacías).
    2. Plan cartografico de Fase 4 (center.lat presente).
    3. Estacion climatica seleccionada de Fase 4 (proxy: las coordenadas
       del expediente se usaron para seleccionarla).
    """
    if phase2_data:
        scope = _extract_object_scope(phase2_data)
        if scope.get("coordenadas_wgs84"):
            return True
    if phase4_result:
        cp = phase4_result.get("cartography_plan")
        if cp:
            center = cp.get("center")
            if center and center.get("lat"):
                return True
        climate = phase4_result.get("climate")
        if climate and climate.get("selected_station"):
            return True
    return False


def _get_effective_plan(
    phase4_result: dict | None,
    cartography_plan: dict | None,
) -> dict | None:
    """Devuelve el plan cartografico efectivo: argumento externo o embebido en Fase 4."""
    if cartography_plan is not None:
        return cartography_plan
    if phase4_result:
        return phase4_result.get("cartography_plan")
    return None


def _has_maps_in_plan(plan: dict | None) -> bool:
    """True si el plan cartografico contiene al menos un MapSpec planificado."""
    if not plan:
        return False
    return bool(plan.get("maps", []))


# ---------------------------------------------------------------------------
# ContextInventoryBuildResult
# ---------------------------------------------------------------------------

@dataclass
class ContextInventoryBuildResult:
    """Resultado del constructor de factores de contexto desde Fase 2/Fase 4 offline (IV-04)."""

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
        lines = [f"Factores de contexto IV-04 -- {len(self.factors)} factor(es)"]
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
# build_landscape_factor_from_phase_data
# ---------------------------------------------------------------------------

def build_landscape_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-011 Paisaje desde los outputs de Fase 2/Fase 4 offline.

    Reglas de prudencia:
    - inventory_semaphore nunca es VERDE en modo offline.
    - ready_for_impact_assessment siempre False.
    - No se afirma calidad paisajistica, fragilidad del paisaje ni magnitud
      de la alteracion visual.
    - Gap GAP-FI-011-001 siempre presente (caracterizacion paisajistica pendiente).

    Args:
        phase2_data:      Dict de Phase2Result.to_dict() (opcional).
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (opcional).
        cartography_plan: Dict de CartographyPlanResult.to_dict() (opcional;
                          si None se usa el embebido en phase4_result).

    Returns:
        FactorInventory para FI-011 Paisaje con semaforo AMARILLO o NO_CONSTA.
    """
    effective_plan = _get_effective_plan(phase4_result, cartography_plan)
    has_plan = bool(effective_plan)
    has_coords = _has_location(phase2_data, phase4_result)
    has_maps = _has_maps_in_plan(effective_plan)

    warnings: list[str] = []
    notes: list[str] = []

    # --- Nivel de evidencia ---
    # Semaforo: AMARILLO solo si hay tanto coordenadas como plan cartografico.
    has_any_spatial = has_coords or has_plan

    if has_coords and has_plan:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "AMARILLO"
    elif has_any_spatial:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        semaphore = "NO_CONSTA"
        warnings.append(
            "Datos espaciales parciales para FI-011 Paisaje: "
            "se requieren tanto coordenadas como plan cartografico para semaforo AMARILLO."
        )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        semaphore = "NO_CONSTA"
        warnings.append(
            "No se dispone de coordenadas ni plan cartografico de Fase 4. "
            "FI-011 Paisaje no puede evaluarse en modo offline."
        )

    # --- Description ---
    parts: list[str] = [
        "Paisaje evaluado en modo gabinete a partir de los datos disponibles "
        "en Fase 2 (OB-06) y Fase 4 (F4-01)."
    ]

    if has_plan:
        n_maps = len(effective_plan.get("maps", []))
        if has_maps:
            parts.append(
                f"El plan cartografico offline (CA-10) incluye {n_maps} mapa(s) previsto(s) "
                "para el emplazamiento."
            )
        else:
            parts.append(
                "El plan cartografico offline (CA-10) fue generado, "
                "pero no contiene mapas especificos planificados."
            )

    if has_coords:
        parts.append(
            "Las coordenadas del emplazamiento estan disponibles en los datos de Fase 4, "
            "lo que permite referir geograficamente el analisis paisajistico."
        )

    if phase2_data:
        scope = _extract_object_scope(phase2_data)
        titular = scope.get("titular")
        if titular:
            parts.append(f"La actividad es promovida por {titular}.")

    parts.append(
        "La evaluacion del paisaje requiere analisis visual del entorno real y consulta "
        "de cartografia oficial antes del Documento Ambiental definitivo. "
        "Las fuentes de gabinete permiten orientar el analisis pero no permiten "
        "determinar la calidad paisajistica ni valorar la posible alteracion visual "
        "del proyecto sobre el entorno."
    )
    parts.append(
        "No se formula juicio sobre calidad paisajistica, fragilidad del paisaje "
        "ni magnitud de ninguna alteracion visual con los datos de Fase 2/Fase 4 offline."
    )

    description = " ".join(parts)

    # --- Data sources ---
    data_sources: list[str] = []
    if phase2_data:
        data_sources.append("OB-06 -- Object scope Fase 2 (datos declarados)")
    if phase4_result:
        data_sources.append("F4-01 -- Pipeline Fase 4 offline")
    if has_plan:
        data_sources.append("CA-10 -- Plan cartografico offline")
    if has_maps:
        data_sources.append(
            "CA-11 -- Mapas esquematicos offline (provisional, orientativo)"
        )
    if not data_sources:
        data_sources.append(
            "Sin datos de Fase 2 ni Fase 4 disponibles"
        )
    data_sources.append(
        "Fuente oficial pendiente: cartografia de paisaje, catalogo regional de paisaje "
        "u organismo autonómico competente"
    )

    # --- Notes ---
    notes.append(
        "FI-011 Paisaje: la caracterizacion oficial requiere analisis visual del entorno "
        "real y consulta de cartografia especifica de paisaje. "
        "La evaluacion de gabinete es orientativa y no apta para el DA definitivo."
    )

    # --- Gap obligatorio GAP-FI-011-001 ---
    gap = InventoryGap(
        gap_id="GAP-FI-011-001",
        factor_id="FI-011",
        field="caracterizacion_paisajistica_oficial",
        description=(
            "Pendiente de caracterizacion paisajistica oficial mediante analisis visual "
            "del entorno real o consulta de cartografia de paisaje especifica. "
            "La evaluacion de gabinete no permite determinar la calidad paisajistica, "
            "la fragilidad del paisaje ni la posible magnitud de la alteracion visual. "
            "Requiere analisis previo al DA definitivo."
        ),
        criticality="MEDIA",
        resolution_mode="CAMPO",
        status="PENDIENTE",
    )

    # --- Justificaciones ---
    if has_coords and has_plan:
        field_mode_just = (
            "La evaluacion paisajistica requiere analisis visual y cartografia especifica. "
            "Se recomienda inspeccion del entorno o consulta de cartografia oficial del paisaje "
            "antes de la valoracion de impactos."
        )
        sem_just = (
            "Semaforo AMARILLO: se dispone de coordenadas y plan cartografico offline "
            "que permiten referir geograficamente el analisis paisajistico. "
            "No puede calificarse VERDE sin caracterizacion paisajistica oficial."
        )
    elif has_any_spatial:
        field_mode_just = (
            "Datos espaciales parciales disponibles. "
            "Se recomienda completar con cartografia oficial antes del DA definitivo."
        )
        sem_just = ""
    else:
        field_mode_just = ""
        sem_just = ""

    return FactorInventory(
        factor_id="FI-011",
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
# build_socioeconomic_factor_from_phase_data
# ---------------------------------------------------------------------------

def build_socioeconomic_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
) -> FactorInventory:
    """Construye FI-013 Socioeconomia desde los outputs de Fase 2/Fase 4 offline.

    Reglas de prudencia:
    - No se afirma generacion de empleo salvo que conste en documentacion.
    - No se cuantifican efectos socioeconomicos especificos.
    - El factor socioeconomico no sustituye ni anula la valoracion de
      los impactos ambientales negativos.
    - inventory_semaphore no sera VERDE salvo justificacion documentada.
    - Gap GAP-FI-013-001 siempre presente (compatibilidad urbanistica pendiente).

    Args:
        phase2_data:   Dict de Phase2Result.to_dict() (opcional).
        phase4_result: Dict de Phase4OfflineResult.to_dict() (opcional).

    Returns:
        FactorInventory para FI-013 Socioeconomia con semaforo AMARILLO o NO_CONSTA.
    """
    scope = _extract_object_scope(phase2_data)

    titular = scope.get("titular") or None
    operaciones_incluidas: list = scope.get("operaciones_incluidas") or []
    coordenadas_wgs84: list = scope.get("coordenadas_wgs84") or []
    superficie_m2 = scope.get("superficie_m2") or None

    has_promoter = bool(titular)
    has_activity = bool(operaciones_incluidas)
    has_location = bool(coordenadas_wgs84) or _has_location(None, phase4_result)

    warnings: list[str] = []
    notes: list[str] = []

    # --- Nivel de evidencia ---
    if has_promoter and has_activity:
        evidence_status = "DECLARADO"
    else:
        evidence_status = "PENDIENTE"
        if not has_promoter:
            warnings.append(
                "No consta titular ni promotor en los datos de Fase 2. "
                "FI-013 Socioeconomia no puede caracterizarse sin datos del promotor."
            )
        if not has_activity:
            warnings.append(
                "No constan operaciones incluidas en el objeto evaluado. "
                "FI-013 Socioeconomia requiere la descripcion de la actividad."
            )

    # --- Field mode ---
    if has_promoter and has_activity and has_location:
        field_mode = "GABINETE_SUFICIENTE"
        ready = True
    else:
        field_mode = "NO_CONSTA"
        ready = False

    # --- Semaforo ---
    # Mantenido manual para garantizar que nunca supera AMARILLO en modo offline.
    if evidence_status == "DECLARADO":
        semaphore = "AMARILLO"
    else:
        semaphore = "NO_CONSTA"

    # --- Description ---
    parts: list[str] = [
        "Socioeconomia evaluada en modo gabinete a partir de los datos declarados "
        "en la documentacion del promotor procesados en Fase 2 (OB-06)."
    ]

    if has_promoter:
        parts.append(f"Promotor de la actividad: {titular}.")
    else:
        parts.append(
            "No consta titular ni promotor en los datos procesados hasta el momento."
        )

    if has_activity:
        ops_str = "; ".join(str(op) for op in operaciones_incluidas[:3])
        if len(operaciones_incluidas) > 3:
            ops_str += f" (y {len(operaciones_incluidas) - 3} operacion(es) adicional(es))"
        parts.append(f"Operaciones incluidas en el objeto evaluado: {ops_str}.")
    else:
        parts.append(
            "No constan operaciones incluidas en el objeto evaluado."
        )

    if superficie_m2:
        parts.append(f"Superficie declarada: {superficie_m2}.")

    if has_location:
        parts.append(
            "La ubicacion del emplazamiento consta en los datos de Fase 2/Fase 4, "
            "lo que permite referir el analisis socioeconomico a un ambito territorial."
        )

    parts.append(
        "La actividad puede tener una contribucion funcional en el contexto economico local "
        "en funcion de su naturaleza y dimensiones, pero no se cuantifican efectos "
        "socioeconomicos especificos en esta evaluacion offline. "
        "No se afirma generacion de empleo ni cuantificacion economica "
        "salvo que conste expresamente en la documentacion del promotor."
    )
    parts.append(
        "El analisis socioeconomico no sustituye ni anula la valoracion de los impactos "
        "ambientales del proyecto en la evaluacion de la significancia."
    )

    description = " ".join(parts)

    # --- Data sources ---
    data_sources: list[str] = []
    if phase2_data:
        data_sources.append("OB-06 -- Object scope Fase 2 (datos declarados)")
    if phase4_result:
        data_sources.append("F4-01 -- Pipeline Fase 4 offline")
    if not data_sources:
        data_sources.append("Sin datos de Fase 2 disponibles")

    # --- Notes ---
    notes.append(
        "FI-013 Socioeconomia: basado exclusivamente en datos declarados por el promotor. "
        "No se ha realizado analisis economico independiente ni consulta de estadisticas. "
        "No se cuantifican efectos socioeconomicos especificos."
    )
    if has_promoter and has_activity:
        notes.append(
            "Datos minimos disponibles para caracterizacion socioeconomica de gabinete. "
            "Verificar compatibilidad urbanistica antes del DA definitivo."
        )

    # --- Gaps ---
    gaps: list[InventoryGap] = []

    # GAP-FI-013-001: compatibilidad urbanistica (siempre presente en modo offline)
    gaps.append(InventoryGap(
        gap_id="GAP-FI-013-001",
        factor_id="FI-013",
        field="compatibilidad_urbanistica",
        description=(
            "No consta verificacion de la compatibilidad urbanistica de la actividad "
            "con el planeamiento municipal vigente. "
            "La compatibilidad urbanistica condiciona la viabilidad del proyecto "
            "y debe verificarse con el planeamiento antes del DA definitivo."
        ),
        criticality="MEDIA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    ))

    # GAP-FI-013-002: datos promotor/actividad (solo si faltan datos minimos)
    if not has_promoter or not has_activity:
        gaps.append(InventoryGap(
            gap_id="GAP-FI-013-002",
            factor_id="FI-013",
            field="datos_promotor_actividad",
            description=(
                "No constan datos suficientes del promotor o de las operaciones incluidas. "
                "Se requiere identificacion clara del titular y descripcion de la actividad "
                "para caracterizar el factor socioeconomico."
            ),
            criticality="ALTA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        ))

    # --- Justificaciones ---
    if field_mode == "GABINETE_SUFICIENTE":
        field_mode_just = (
            "Se dispone de datos declarados del promotor, actividad y ubicacion "
            "suficientes para la caracterizacion socioeconomica de gabinete. "
            "No se requiere trabajo de campo adicional para este factor en EIA simplificada."
        )
    else:
        field_mode_just = ""

    if evidence_status == "DECLARADO":
        sem_just = (
            "Semaforo AMARILLO: se dispone de datos declarados del promotor y la actividad "
            "procedentes de la documentacion del expediente. "
            "La compatibilidad urbanistica queda pendiente de verificacion."
        )
    else:
        sem_just = ""

    return FactorInventory(
        factor_id="FI-013",
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=semaphore,
        description=description,
        data_sources=data_sources,
        gaps=gaps,
        ready_for_impact_assessment=ready,
        warnings=warnings,
        notes=notes,
        field_mode_justification=field_mode_just,
        semaphore_justification=sem_just,
    )


# ---------------------------------------------------------------------------
# build_context_inventory_factors_from_phase_data
# ---------------------------------------------------------------------------

def build_context_inventory_factors_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> ContextInventoryBuildResult:
    """Construye FI-011 e FI-013 desde los outputs de Fase 2/Fase 4 offline.

    Args:
        phase2_data:      Dict de Phase2Result.to_dict() (opcional).
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (opcional).
        cartography_plan: Dict de CartographyPlanResult.to_dict() (opcional).

    Returns:
        ContextInventoryBuildResult con [FI-011, FI-013], warnings y notes.
    """
    warnings: list[str] = []
    notes: list[str] = []

    fi011 = build_landscape_factor_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=cartography_plan,
    )
    fi013 = build_socioeconomic_factor_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
    )

    if not phase2_data:
        warnings.append(
            "No se dispone de datos de Fase 2 (phase2_result.json). "
            "FI-013 queda en PENDIENTE/NO_CONSTA. "
            "Ejecutar OB-06 para enriquecer este factor."
        )

    effective = _get_effective_plan(phase4_result, cartography_plan)
    if not effective:
        warnings.append(
            "No se dispone de plan cartografico en Fase 4. "
            "FI-011 Paisaje queda limitado a los datos de Fase 2. "
            "Ejecutar CA-10 y F4-01 para enriquecer este factor."
        )

    notes.append(
        "Factores de contexto FI-011 e FI-013 construidos en modo offline (IV-04). "
        "FI-011 ready_for_impact_assessment siempre False. "
        "FI-013 ready solo si hay promotor, actividad y ubicacion declarados."
    )

    return ContextInventoryBuildResult(
        factors=[fi011, fi013],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# merge_context_factors_into_summary
# ---------------------------------------------------------------------------

def merge_context_factors_into_summary(
    summary: InventorySummary,
    context_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-011 y FI-013 en un InventorySummary existente.

    No muta el summary original. Crea un nuevo InventorySummary con los
    factores de contexto reemplazados. Conserva el orden canonico de factores
    y propaga los warnings/notes del summary original.

    Args:
        summary:         InventorySummary original (no se muta).
        context_factors: Lista de FactorInventory a sustituir (FI-011, FI-013 o ambos).

    Returns:
        Nuevo InventorySummary con 16 factores (sin duplicados).
    """
    context_ids = {f.factor_id for f in context_factors}

    new_factors: list[FactorInventory] = []
    for existing in summary.factors:
        if existing.factor_id in context_ids:
            replacement = next(
                f for f in context_factors if f.factor_id == existing.factor_id
            )
            new_factors.append(replacement)
        else:
            new_factors.append(existing)

    new_summary = build_inventory_summary(summary.expediente_id, new_factors)

    # Propagar warnings y notes del summary original
    new_summary.warnings.extend(summary.warnings)
    new_summary.notes.extend(summary.notes)

    return new_summary
