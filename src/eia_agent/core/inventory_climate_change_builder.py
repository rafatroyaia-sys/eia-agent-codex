"""
inventory_climate_change_builder -- IV-08
Constructor de factor FI-015 Cambio climatico desde Fase 2/Fase 4 offline.

Integra los datos climaticos de CL-06 (clasificacion Koppen-Geiger, temperatura,
precipitacion, indice de aridez) con la descripcion de actividad/equipos de
Fase 2 para construir FI-015 con:
  - contexto climatico del emplazamiento procedente de CL-06;
  - deteccion de posibles fuentes de GEI por presencia textual de terminos;
  - vulnerabilidades climaticas preliminares;
  - gaps de caracterizacion pendientes.

Reglas de prudencia:
  - No se cuantifican emisiones ni huella de carbono.
  - No se afirma "sin emisiones", "carbono neutro", "emisiones despreciables".
  - No se afirma "impacto climatico compatible", "riesgo climatico bajo".
  - No se usan: COMPATIBLE, MODERADO, SEVERO, CRITICO en valoracion de impacto.
  - ready_for_impact_assessment: False siempre en modo offline.
  - inventory_semaphore: nunca VERDE en modo offline sin datos de consumos/emisiones.

No calcula huella de carbono.
No cuantifica emisiones GEI.
No verifica consumos energeticos ni combustibles.
No sustituye analisis de cambio climatico especifico.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) -- FactorInventory, InventoryGap, InventorySummary
  CL-06 (phase4_climate_pipeline) -- datos climaticos CL-06
  F4-01 (phase4_offline_pipeline) -- estructura phase4_result.json
  OB-06 (phase2_pipeline) -- estructura phase2_result.json (opcional)
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

_GHG_TERMS: tuple[str, ...] = (
    "diesel",
    "gasoil",
    "combustion",
    "combustión",
    "motor",
    "generador",
    "carretilla",
    "transporte",
    "camion",
    "camión",
    "electricidad",
    "potencia",
    "consumo",
    "compresor",
    "maquinaria",
    "furgoneta",
    "vehiculo",
    "vehículo",
    "caldera",
    "quemador",
    "horno",
    "incineracion",
    "incineración",
)

_GHG_HIGH_TERMS: frozenset[str] = frozenset({
    "diesel",
    "gasoil",
    "combustion",
    "combustión",
    "generador",
    "carretilla",
    "camion",
    "camión",
    "caldera",
    "quemador",
    "horno",
    "incineracion",
    "incineración",
})

_VULNERABILITY_TERMS: tuple[str, ...] = (
    "dana",
    "inundabilidad",
    "sequia",
    "sequía",
    "aridez",
    "altas temperaturas",
    "calor extremo",
    "precipitacion intensa",
    "precipitación intensa",
    "riesgo natural",
    "escorrentia",
    "escorrentía",
    "ola de calor",
    "tormenta",
    "viento fuerte",
    "granizo",
    "inundacion",
    "inundación",
)

_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "combustion",
    "combustión",
    "diesel",
    "gasoil",
    "motor",
    "generador",
    "carretilla",
    "electricidad",
    "potencia",
    "consumo",
    "transporte",
    "clima",
    "temperatura",
    "precipitacion",
    "precipitación",
    "aridez",
    "sequia",
    "sequía",
    "dana",
    "cambio climatico",
    "cambio climático",
    "riesgo natural",
    "vulnerabilidad",
    "koppen",
    "martonne",
    "inundab",
    "escorrent",
)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------


def extract_climate_change_context(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    climate_result: dict | None = None,
) -> str:
    """Extrae texto relacionado con cambio climatico/GEI de los datos disponibles.

    Recorre de forma segura dicts y listas buscando menciones a:
    combustion, diesel, electricidad, clima, temperatura, precipitacion,
    aridez, sequia, DANA, cambio climatico, vulnerabilidad, etc.

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
    _scrape(climate_result)

    return " ".join(parts)


def detect_ghg_relevant_sources(text: str) -> list[str]:
    """Detecta terminos de fuentes potenciales de GEI en texto de actividad.

    Devuelve lista de terminos encontrados (sin duplicados, en orden de aparicion).
    """
    found: list[str] = []
    for term in _GHG_TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def detect_climate_vulnerability_terms(text: str) -> list[str]:
    """Detecta terminos de vulnerabilidad climatica en texto disponible.

    Devuelve lista de terminos encontrados (sin duplicados, en orden de aparicion).
    """
    found: list[str] = []
    for term in _VULNERABILITY_TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def _extract_activity_text(phase2_data: dict | None) -> str:
    """Extrae texto de operaciones incluidas de phase2_data en minusculas."""
    if not phase2_data:
        return ""
    scope = phase2_data.get("object_scope") or {}
    ops = scope.get("operaciones_incluidas") or []
    parts: list[str] = []
    if isinstance(ops, list):
        parts.extend(str(op) for op in ops if op)
    elif isinstance(ops, str) and ops:
        parts.append(ops)
    desc = scope.get("descripcion_actividad") or scope.get("actividad") or ""
    if desc:
        parts.append(str(desc))
    nombre = scope.get("denominacion") or scope.get("nombre_proyecto") or ""
    if nombre:
        parts.append(str(nombre))
    return " ".join(parts).lower()


def _extract_climate_summary(climate_result: dict | None) -> dict:
    """Extrae los campos clave del resultado climatico en un dict simplificado."""
    if not climate_result:
        return {}
    cc = climate_result.get("climate_classification") or {}
    station = climate_result.get("selected_station") or {}
    return {
        "station_name": station.get("name"),
        "station_id": station.get("station_id"),
        "distance_km": climate_result.get("station_distance_km"),
        "selection_status": climate_result.get("station_selection_status"),
        "koppen_code": cc.get("koppen_code"),
        "koppen_label": cc.get("koppen_label"),
        "temp_c": cc.get("annual_temperature_c"),
        "precip_mm": cc.get("annual_precipitation_mm"),
        "martonne_index": cc.get("martonne_index"),
        "martonne_label": cc.get("martonne_label"),
        "dry_months": (lambda v: v if isinstance(v, int) else len(v) if v else 0)(cc.get("dry_months_gaussen")),
        "dry_months_names": cc.get("dry_months_names") or [],
    }


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class ClimateChangeInventoryBuildResult:
    """Resultado de IV-08: FI-015 Cambio climatico."""

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
            "ClimateChangeInventoryBuildResult:",
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
# Constructor FI-015 Cambio climatico
# ---------------------------------------------------------------------------


def build_climate_change_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    climate_result: dict | None = None,
) -> FactorInventory:
    """Construye FI-015 Cambio climatico desde datos de Fase 2 y Fase 4.

    Fuentes usadas:
      - climate_result (CL-06): clasificacion Koppen, temperatura, precipitacion, aridez.
      - phase2_data.object_scope.operaciones_incluidas: deteccion de fuentes GEI.
      - phase4_result: datos complementarios y vulnerabilidades.

    Logica de evidencia:
      - DECLARADO si hay clima CL-06 y actividad declarada.
      - ESTIMADO si solo hay clima O solo hay actividad.
      - PENDIENTE si no hay datos utiles.

    Logica de semaforo:
      - ROJO_AMARILLO si hay fuentes claras de combustion/diesel sin datos de consumo.
      - AMARILLO si hay clima + actividad pero sin fuentes de combustion documentadas.
      - NO_CONSTA si no hay datos.
      - Nunca VERDE.

    Logica de field_mode:
      - CAMPO_RECOMENDADO si hay fuentes de GEI detectadas (combustion/diesel).
      - GABINETE_SUFICIENTE si hay clima + actividad sin fuentes de combustion directa.
      - NO_CONSTA si sin informacion.

    GAP-FI-015-001: caracterizacion GEI — ALTA si combustion, MEDIA si solo electricidad.
    GAP-FI-015-002: analisis adaptacion/vulnerabilidad — MEDIA siempre.
    ready_for_impact_assessment: False siempre en modo offline.
    """
    fid = "FI-015"
    fname = FACTOR_NAMES.get(fid, "Cambio climatico")

    # Resolver datos climaticos
    effective_climate = climate_result
    if effective_climate is None and phase4_result:
        effective_climate = phase4_result.get("climate")

    climate_summary = _extract_climate_summary(effective_climate)
    has_climate = bool(climate_summary.get("koppen_code") or climate_summary.get("station_name"))

    # Texto de actividad
    activity_text = _extract_activity_text(phase2_data)
    # Tambien texto del propio phase4_result para vulnerabilidades
    all_text = extract_climate_change_context(phase2_data, phase4_result, effective_climate)

    has_activity = bool(activity_text.strip())
    ghg_terms = detect_ghg_relevant_sources(activity_text)
    vuln_terms = detect_climate_vulnerability_terms(all_text)
    has_high_ghg = any(t in _GHG_HIGH_TERMS for t in ghg_terms)

    # --- Evidence status ---
    if has_climate and has_activity:
        evidence_status = "DECLARADO"
    elif has_climate or has_activity:
        evidence_status = "ESTIMADO"
    else:
        evidence_status = "PENDIENTE"

    # --- Field mode ---
    if evidence_status == "PENDIENTE":
        field_mode = "NO_CONSTA"
    elif ghg_terms:
        field_mode = "CAMPO_RECOMENDADO"
    else:
        field_mode = "GABINETE_SUFICIENTE"

    # --- Semaphore ---
    if evidence_status == "PENDIENTE":
        inventory_semaphore = "NO_CONSTA"
    elif has_high_ghg:
        inventory_semaphore = "ROJO_AMARILLO"
    elif has_climate or has_activity:
        inventory_semaphore = "AMARILLO"
    else:
        inventory_semaphore = "NO_CONSTA"

    # --- Data sources ---
    data_sources: list[str] = []
    if has_climate:
        data_sources.append("CL-06 — pipeline climatico offline (datos AEMET)")
        data_sources.append("F4-01 — plan de Fase 4 offline")
    elif phase4_result:
        data_sources.append("F4-01 — plan de Fase 4 offline")
    if has_activity:
        data_sources.append("OB-06 — documentacion del promotor (Fase 2)")

    # --- Description ---
    desc_parts: list[str] = []

    if has_climate:
        cs = climate_summary
        if cs.get("station_name"):
            dist = cs.get("distance_km")
            dist_str = f" a {dist:.1f} km" if dist is not None else ""
            status_map = {
                "OPTIMA": "optima",
                "ACEPTABLE": "aceptable",
                "LEJANA": "lejana",
                "NO_DISPONIBLE": "no disponible",
            }
            sel_str = status_map.get(cs.get("selection_status", ""), cs.get("selection_status", ""))
            desc_parts.append(
                f"Estacion de referencia climatica: {cs['station_name']} "
                f"({cs.get('station_id', '?')}){dist_str}, seleccion {sel_str}."
            )
        if cs.get("koppen_code"):
            desc_parts.append(
                f"Clasificacion climatica Koppen-Geiger: {cs['koppen_code']} "
                f"({cs.get('koppen_label', 'clasificacion no disponible')})."
            )
        if cs.get("temp_c") is not None:
            desc_parts.append(f"Temperatura media anual: {cs['temp_c']:.1f} °C.")
        if cs.get("precip_mm") is not None:
            desc_parts.append(f"Precipitacion media anual: {cs['precip_mm']:.1f} mm.")
        if cs.get("martonne_index") is not None:
            desc_parts.append(
                f"Indice de aridez de Martonne: {cs['martonne_index']:.1f} "
                f"({cs.get('martonne_label', '')})."
            )
        if cs.get("dry_months") is not None:
            dry = cs["dry_months"]
            if dry == 12:
                desc_parts.append("Regimen hidrico: arido extremo con los 12 meses secos.")
            elif dry > 0:
                dry_names = cs.get("dry_months_names") or []
                if dry_names:
                    desc_parts.append(
                        f"Meses secos (indice de Gaussen): {dry} "
                        f"({', '.join(dry_names[:6])}{'...' if len(dry_names) > 6 else ''})."
                    )

    if ghg_terms:
        desc_parts.append(
            f"Se detectan posibles fuentes de emisiones de GEI a partir de la "
            f"descripcion de actividad declarada: "
            f"{', '.join(ghg_terms[:6])}{'...' if len(ghg_terms) > 6 else ''}. "
            "No se dispone de datos de consumo energetico ni cuantificacion de emisiones. "
            "La presencia de estas fuentes no implica ninguna valoracion del impacto climatico."
        )
    elif has_activity:
        desc_parts.append(
            "La descripcion de actividad declarada no incluye fuentes de emision de GEI "
            "claramente identificables. No se descarta la existencia de consumos energeticos "
            "o emisiones asociados a la operacion."
        )

    if vuln_terms:
        desc_parts.append(
            f"Se identifican terminos de relevancia para la vulnerabilidad climatica "
            f"del emplazamiento: {', '.join(vuln_terms[:5])}. "
            "Estos terminos proceden del contexto de datos disponibles y requieren "
            "analisis especifico de adaptacion antes del Documento Ambiental."
        )

    desc_parts.append(
        "Esta caracterizacion es preliminar de gabinete. "
        "No existe cuantificacion de emisiones ni huella de carbono en esta version. "
        "El analisis de cambio climatico en el Documento Ambiental requiere "
        "caracterizacion de consumos, inventario de GEI y analisis de vulnerabilidad "
        "y adaptacion especificos."
    )

    description = " ".join(desc_parts)

    # --- Gaps ---
    gap_gei_criticality = "ALTA" if has_high_ghg else "MEDIA"
    gap_gei = InventoryGap(
        gap_id="GAP-FI-015-001",
        factor_id="FI-015",
        field="caracterizacion_consumos_gei",
        description=(
            "Pendiente caracterizacion de consumos energeticos, combustibles utilizados "
            "y estimacion de emisiones de GEI asociadas a la actividad. "
            "Requiere aportacion del promotor de datos de consumo electrico, combustibles "
            "y cualquier otra fuente de emision directa o indirecta antes del DA definitivo."
        ),
        criticality=gap_gei_criticality,
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    gap_adapt = InventoryGap(
        gap_id="GAP-FI-015-002",
        factor_id="FI-015",
        field="analisis_adaptacion_vulnerabilidad",
        description=(
            "Pendiente analisis especifico de adaptacion al cambio climatico y "
            "vulnerabilidad del proyecto frente a los riesgos climaticos identificados "
            "(aridez, eventos extremos, DANA u otros segun CCAA). "
            "Requiere consulta al Plan Nacional de Adaptacion al Cambio Climatico (PNACC) "
            "y normativa autonomica aplicable."
        ),
        criticality="MEDIA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    return FactorInventory(
        factor_id=fid,
        factor_name=fname,
        evidence_status=evidence_status,
        field_mode=field_mode,
        inventory_semaphore=inventory_semaphore,
        description=description,
        data_sources=data_sources,
        gaps=[gap_gei, gap_adapt],
        ready_for_impact_assessment=False,
    )


# ---------------------------------------------------------------------------
# Constructor con resultado
# ---------------------------------------------------------------------------


def build_climate_change_inventory_factor_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    climate_result: dict | None = None,
) -> ClimateChangeInventoryBuildResult:
    """Construye FI-015 y lo devuelve como ClimateChangeInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    fi015 = build_climate_change_factor_from_phase_data(phase2_data, phase4_result, climate_result)

    if fi015.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-015 Cambio climatico: sin datos climaticos de CL-06 ni descripcion "
            "de actividad. Pendiente caracterizacion de Fase 2 y Fase 4."
        )
    elif fi015.evidence_status == "ESTIMADO":
        if not climate_result and not (phase4_result or {}).get("climate"):
            warnings.append(
                "FI-015 Cambio climatico: sin datos climaticos de CL-06. "
                "Solo datos de actividad disponibles."
            )
        else:
            notes.append(
                "FI-015 Cambio climatico: sin descripcion de actividad de Fase 2. "
                "Solo contexto climatico disponible."
            )

    notes.append(
        f"IV-08: FI-015={fi015.evidence_status}/{fi015.inventory_semaphore}. "
        f"GEI detectados: {bool(detect_ghg_relevant_sources(_extract_activity_text(phase2_data)))}. "
        "Cuantificacion de emisiones pendiente."
    )

    return ClimateChangeInventoryBuildResult(
        factor=fi015,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_climate_change_factor_into_summary(
    summary: InventorySummary,
    factor: FactorInventory,
) -> InventorySummary:
    """Sustituye FI-015 en un InventorySummary sin mutar el original.

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
