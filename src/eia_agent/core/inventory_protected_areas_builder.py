"""
inventory_protected_areas_builder -- IV-06
Constructor de factores FI-009 Espacios Naturales Protegidos y FI-010 Red Natura 2000
desde Fase 4 offline.

Lee los outputs de Fase 4 (phase4_result.json, cartography_plan.json) y construye
los factores FI-009 e FI-010 con estado ESTIMADO/PENDIENTE y semaforo AMARILLO/NO_CONSTA
segun la informacion disponible en el plan cartografico offline.

Reglas de prudencia aplicadas:
  - FI-009: no se afirma ausencia de Espacios Naturales Protegidos.
    No se afirma "no hay ENP", "fuera de espacios protegidos" ni "sin afecion".
    La verificacion oficial siempre queda pendiente (GAP ALTA).
  - FI-010: no se afirma ausencia de Red Natura 2000.
    No se afirma "no hay Red Natura", "sin afecion apreciable" ni
    "sin afecion significativa". La decision sobre evaluacion de
    repercusiones corresponde al organo ambiental.
  - ready_for_impact_assessment: False siempre.
  - inventory_semaphore: nunca VERDE en modo offline sin WMS/WMTS oficial.

No consulta WMS ni WMTS.
No consulta visores oficiales (MITERD, Grafcan, REDIAM, etc.).
No verifica presencia/ausencia real de ENP ni Red Natura 2000.
No concluye ausencia de afecion apreciable.
No activa ni descarta evaluacion de repercusiones.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) -- FactorInventory, InventoryGap, InventorySummary
  F4-01 (phase4_offline_pipeline) -- estructura phase4_result.json
  CA-10 (cartography_plan) -- estructura cartography_plan.json
  CA-11 (schematic_maps) -- mapas esquematicos offline
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
# Constantes de deteccion
# ---------------------------------------------------------------------------

_RED_NATURA_MAP_TYPES: frozenset[str] = frozenset({"red_natura_enp"})
_RED_NATURA_LAYERS: frozenset[str] = frozenset({"red_natura_2000"})
_ENP_LAYERS: frozenset[str] = frozenset({"espacios_naturales_protegidos"})
_MAP004_ID: str = "MAP-004"

_PROT_AREA_KEYWORDS: tuple[str, ...] = (
    "red natura",
    "red_natura",
    "natura 2000",
    "natura2000",
    "lic",
    "zec",
    "zepa",
    "spa",
    "enp",
    "espacio natural",
    "espacio protegido",
    "parque natural",
    "parque nacional",
    "reserva natural",
    "monumento natural",
    "paisaje protegido",
    "red_natura_enp",
    "espacios_naturales_protegidos",
    "map-004",
)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------


def _iter_maps(cartography_plan: dict | None) -> list[dict]:
    """Devuelve la lista de MapSpec dicts del plan, o lista vacia."""
    if not cartography_plan:
        return []
    maps = cartography_plan.get("maps") or []
    return [m for m in maps if isinstance(m, dict)]


def has_red_natura_map_planned(cartography_plan: dict | None = None) -> bool:
    """Devuelve True si el plan cartografico incluye un mapa de Red Natura / ENP.

    Detecta:
      - map_type == 'red_natura_enp'
      - map_id == 'MAP-004'
      - required_layers contiene 'red_natura_2000'
    """
    for m in _iter_maps(cartography_plan):
        if m.get("map_type") in _RED_NATURA_MAP_TYPES:
            return True
        if m.get("map_id") == _MAP004_ID:
            return True
        layers = m.get("required_layers") or []
        if any(lay in _RED_NATURA_LAYERS for lay in layers):
            return True
    return False


def has_enp_map_planned(cartography_plan: dict | None = None) -> bool:
    """Devuelve True si el plan cartografico incluye un mapa de ENP.

    Detecta:
      - map_type == 'red_natura_enp'
      - map_id == 'MAP-004'
      - required_layers contiene 'espacios_naturales_protegidos'
    """
    for m in _iter_maps(cartography_plan):
        if m.get("map_type") in _RED_NATURA_MAP_TYPES:
            return True
        if m.get("map_id") == _MAP004_ID:
            return True
        layers = m.get("required_layers") or []
        if any(lay in _ENP_LAYERS for lay in layers):
            return True
    return False


def extract_protected_area_context(
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> str:
    """Extrae texto relacionado con ENP/Red Natura de los datos de Fase 4.

    Recorre de forma segura dicts y listas buscando menciones a:
    - Red Natura 2000, LIC, ZEC, ZEPA, ENP, espacios protegidos
    - MAP-004 y capas red_natura_2000 / espacios_naturales_protegidos

    Devuelve str en minusculas con el contenido relevante encontrado.
    """
    parts: list[str] = []

    def _scrape(obj: object, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(obj, str):
            lo = obj.lower()
            if any(kw in lo for kw in _PROT_AREA_KEYWORDS):
                parts.append(lo)
        elif isinstance(obj, dict):
            for v in obj.values():
                _scrape(v, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _scrape(item, depth + 1)

    _scrape(phase4_result)
    _scrape(cartography_plan)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class ProtectedAreasInventoryBuildResult:
    """Resultado de IV-06: FI-009 ENP + FI-010 Red Natura 2000."""

    factors: list[FactorInventory]
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "factors": [f.to_dict() for f in self.factors],
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = ["ProtectedAreasInventoryBuildResult:"]
        for f in self.factors:
            lines.append(
                f"  {f.factor_id} {f.factor_name}: "
                f"evidence={f.evidence_status} "
                f"field_mode={f.field_mode} "
                f"semaphore={f.inventory_semaphore} "
                f"gaps={len(f.gaps)}"
            )
        if self.warnings:
            lines.append(f"  warnings: {self.warnings}")
        if self.notes:
            lines.append(f"  notes: {self.notes}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Constructor FI-009 Espacios Naturales Protegidos
# ---------------------------------------------------------------------------


def build_enp_factor_from_phase4(
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-009 Espacios Naturales Protegidos desde datos de Fase 4.

    Logica:
      - Sin plan cartografico: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Con plan que incluye mapa ENP (MAP-004 o capa ENP): ESTIMADO / CAMPO_RECOMENDADO / AMARILLO
      - Con plan cartografico sin mapa ENP especifico: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    GAP-FI-009-001: verificacion oficial ENP — siempre, ALTA, GABINETE.
    ready_for_impact_assessment: False siempre.
    inventory_semaphore: nunca VERDE.
    """
    fid = "FI-009"
    fname = FACTOR_NAMES.get(fid, "Espacios Naturales Protegidos")

    data_sources: list[str] = []
    has_plan = bool(cartography_plan)
    has_enp_map = has_enp_map_planned(cartography_plan)
    has_schematic = False

    # Detectar si hay mapas esquematicos generados
    if has_plan:
        for m in _iter_maps(cartography_plan):
            status = m.get("status") or ""
            if "generated" in status.lower() or "provisional" in status.lower():
                has_schematic = True
                break

    if has_plan:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        inventory_semaphore = "AMARILLO"
        data_sources.append("F4-01 — plan cartografico Fase 4 offline")
        data_sources.append("CA-10 — cartography plan")

        if has_enp_map:
            data_sources.append("CA-11 — mapa esquematico MAP-004 Red Natura / ENP")
            description = (
                "El plan cartografico offline contempla el mapa MAP-004 (Red Natura 2000 / ENP) "
                "con las capas de espacios naturales protegidos. "
                "La cartografia esquematica offline es orientativa y no permite concluir "
                "la presencia o ausencia de ENP en el entorno del proyecto. "
                "Se requiere consulta a la fuente oficial autonómica (Grafcan, IECA, REDIAM) "
                "o estatal (MITERD — Banco de Datos de la Naturaleza) antes de la redaccion "
                "del Documento Ambiental definitivo."
            )
        else:
            description = (
                "Existe plan cartografico offline de Fase 4, pero no incluye mapa especifico "
                "de Espacios Naturales Protegidos (MAP-004). "
                "La cartografia disponible no permite determinar la presencia o ausencia "
                "de ENP en el entorno del proyecto. "
                "Se requiere consulta a la fuente oficial autonómica o estatal antes "
                "de la redaccion del Documento Ambiental definitivo."
            )
        if has_schematic:
            description += (
                " Los mapas esquematicos generados (CA-11) tienen caracter provisional "
                "y no sustituyen cartografia oficial."
            )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de plan cartografico ni datos de Fase 4 que permitan "
            "caracterizar la relacion del proyecto con los Espacios Naturales Protegidos. "
            "Se requiere plan cartografico con capa de ENP y consulta a fuente oficial "
            "antes de la redaccion del Documento Ambiental."
        )

    gap = InventoryGap(
        gap_id="GAP-FI-009-001",
        factor_id="FI-009",
        field="verificacion_oficial_enp",
        description=(
            "Pendiente verificacion oficial de la relacion del proyecto con los Espacios "
            "Naturales Protegidos. Requiere consulta al visor oficial autonómico "
            "(Grafcan IdeCAN / IECA / REDIAM segun CCAA) o al Banco de Datos de la "
            "Naturaleza (MITERD). La cartografia offline no es apta para el DA definitivo."
        ),
        criticality="ALTA",
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
        gaps=[gap],
        ready_for_impact_assessment=False,
    )


# ---------------------------------------------------------------------------
# Constructor FI-010 Red Natura 2000
# ---------------------------------------------------------------------------


def build_red_natura_factor_from_phase4(
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-010 Red Natura 2000 desde datos de Fase 4.

    Logica:
      - Sin plan cartografico: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Con plan cartografico: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    GAP-FI-010-001: verificacion oficial Red Natura 2000 — siempre, ALTA, GABINETE.
    ready_for_impact_assessment: False siempre.
    inventory_semaphore: nunca VERDE.
    """
    fid = "FI-010"
    fname = FACTOR_NAMES.get(fid, "Red Natura 2000")

    data_sources: list[str] = []
    has_plan = bool(cartography_plan)
    has_rn_map = has_red_natura_map_planned(cartography_plan)
    has_schematic = False

    if has_plan:
        for m in _iter_maps(cartography_plan):
            status = m.get("status") or ""
            if "generated" in status.lower() or "provisional" in status.lower():
                has_schematic = True
                break

    if has_plan:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        inventory_semaphore = "AMARILLO"
        data_sources.append("F4-01 — plan cartografico Fase 4 offline")
        data_sources.append("CA-10 — cartography plan")

        if has_rn_map:
            data_sources.append("CA-11 — mapa esquematico MAP-004 Red Natura / ENP")
            description = (
                "El plan cartografico offline contempla el mapa MAP-004 "
                "(Red Natura 2000 / ENP) con la capa red_natura_2000. "
                "El analisis realizado en modo offline no permite concluir "
                "la ausencia de afeccion a espacios de la Red Natura 2000. "
                "La decision sobre la necesidad de evaluacion de repercusiones "
                "corresponde al organo ambiental competente, no al promotor. "
                "Se requiere verificacion con WMS/WMTS oficial o consulta al "
                "visor autonómico antes de la redaccion del Documento Ambiental definitivo."
            )
        else:
            description = (
                "Existe plan cartografico offline de Fase 4, pero no incluye mapa especifico "
                "de Red Natura 2000 (MAP-004 / capa red_natura_2000). "
                "El analisis realizado no permite determinar la relacion del proyecto "
                "con la Red Natura 2000. "
                "La decision sobre la necesidad de evaluacion de repercusiones "
                "corresponde al organo ambiental competente. "
                "Se requiere verificacion con fuente oficial antes de la redaccion "
                "del Documento Ambiental definitivo."
            )
        if has_schematic:
            description += (
                " Los mapas esquematicos generados (CA-11) tienen caracter provisional "
                "y no sustituyen cartografia oficial WMS/WMTS."
            )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de plan cartografico ni datos de Fase 4 que permitan "
            "caracterizar la relacion del proyecto con la Red Natura 2000. "
            "La decision sobre la necesidad de evaluacion de repercusiones corresponde "
            "al organo ambiental. Se requiere plan cartografico con capa red_natura_2000 "
            "y verificacion con fuente oficial antes del Documento Ambiental."
        )

    gap = InventoryGap(
        gap_id="GAP-FI-010-001",
        factor_id="FI-010",
        field="verificacion_oficial_red_natura",
        description=(
            "Pendiente verificacion oficial de la relacion del proyecto con la Red Natura 2000 "
            "(LIC, ZEC, ZEPA). Requiere consulta al visor WMS/WMTS oficial autonómico o al "
            "IDE Nacional (Natura 2000 MITERD). La cartografia offline no es suficiente "
            "para descartar ni confirmar afeccion. La evaluacion de repercusiones la "
            "determina el organo ambiental competente."
        ),
        criticality="ALTA",
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
        gaps=[gap],
        ready_for_impact_assessment=False,
    )


# ---------------------------------------------------------------------------
# Constructor combinado
# ---------------------------------------------------------------------------


def build_protected_areas_inventory_factors_from_phase4(
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> ProtectedAreasInventoryBuildResult:
    """Construye FI-009 y FI-010 y los devuelve como ProtectedAreasInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    # Usar plan embebido en phase4_result si no se pasa cartography_plan externo
    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    fi009 = build_enp_factor_from_phase4(phase4_result, effective_plan)
    fi010 = build_red_natura_factor_from_phase4(phase4_result, effective_plan)

    if fi009.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-009 ENP: sin plan cartografico de Fase 4. "
            "Pendiente caracterizacion de Espacios Naturales Protegidos."
        )
    if fi010.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-010 Red Natura: sin plan cartografico de Fase 4. "
            "Pendiente verificacion oficial Red Natura 2000."
        )

    has_rn_map = has_red_natura_map_planned(effective_plan)
    notes.append(
        f"IV-06: FI-009={fi009.evidence_status}/{fi009.inventory_semaphore}, "
        f"FI-010={fi010.evidence_status}/{fi010.inventory_semaphore}. "
        f"MAP-004 planificado: {has_rn_map}. "
        "Verificacion oficial pendiente en ambos factores."
    )

    return ProtectedAreasInventoryBuildResult(
        factors=[fi009, fi010],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_protected_area_factors_into_summary(
    summary: InventorySummary,
    protected_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-009 y/o FI-010 en un InventorySummary sin mutar el original.

    Preserva el orden canonico de FACTOR_NAMES.
    Propaga warnings y notes del summary original.
    """
    merged_map = {f.factor_id: f for f in summary.factors}
    for pf in protected_factors:
        merged_map[pf.factor_id] = pf

    merged_factors = [merged_map[fid] for fid in sorted(FACTOR_NAMES.keys()) if fid in merged_map]

    new_summary = build_inventory_summary(summary.expediente_id, merged_factors)
    new_summary.warnings = list(summary.warnings)
    new_summary.notes = list(summary.notes)
    return new_summary
