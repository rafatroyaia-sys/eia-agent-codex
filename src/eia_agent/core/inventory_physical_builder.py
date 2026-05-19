"""
inventory_physical_builder -- IV-07
Constructor de factores FI-002 Geologia, FI-003 Suelos y FI-004 Hidrologia
desde Fase 4 offline.

Lee los outputs de Fase 4 (phase4_result.json, cartography_plan.json) y,
opcionalmente, los datos de Fase 2 (phase2_result.json / object_scope) para
construir FI-002, FI-003 y FI-004 con estado ESTIMADO/PENDIENTE y semaforo
AMARILLO/NO_CONSTA segun la informacion disponible en el plan cartografico offline.

Reglas de prudencia aplicadas:
  - FI-002: no se afirma "geologia sin interes", "terreno estable" ni
    "sin afecion geologica". La verificacion con IGME/GEODE queda pendiente.
  - FI-003: no se afirma "suelo sin afecion", "sin contaminacion" ni
    "suelo impermeabilizado" salvo dato expreso. La verificacion oficial
    o inspeccion visual queda pendiente.
  - FI-004: no se afirma "no hay cauces", "sin escorrentia", "sin afecion
    hidrologica" ni "sin conectividad hidrica". La verificacion con
    fuente hidrologica oficial queda pendiente.
  - ready_for_impact_assessment: False siempre.
  - inventory_semaphore: nunca VERDE en modo offline.

No consulta IGME, GEODE ni cartografia geologica oficial.
No consulta SIGPAC ni catastro.
No consulta SNCZI ni red hidrologica oficial.
No verifica presencia/ausencia real de cauces, barrancos ni escorrentias.
No acredita estado del suelo ni posible contaminacion.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) -- FactorInventory, InventoryGap, InventorySummary
  F4-01 (phase4_offline_pipeline) -- estructura phase4_result.json
  CA-10 (cartography_plan) -- estructura cartography_plan.json
  CA-11 (schematic_maps) -- mapas esquematicos offline
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
# Palabras clave para deteccion
# ---------------------------------------------------------------------------

_GEOLOGY_KEYWORDS: tuple[str, ...] = (
    "geolog",
    "litolog",
    "igme",
    "geode",
    "roca",
    "sustrato",
    "formacion geol",
    "estratigraf",
    "base geol",
    "riesgos geol",
)

_SOIL_KEYWORDS: tuple[str, ...] = (
    "suelo",
    "usos_suelo",
    "usos del suelo",
    "sigpac",
    "edafolog",
    "corine",
    "siose",
    "ocupacion del suelo",
    "cubierta del suelo",
    "land cover",
    "land use",
    "map-005",
)

_HYDROLOGY_KEYWORDS: tuple[str, ...] = (
    "hidrol",
    "drenaje",
    "inundab",
    "cauce",
    "barranco",
    "escorrent",
    "cuenca",
    "acuifero",
    "snczi",
    "red de drenaje",
    "red fluvial",
    "map-006",
    "vector hidric",
    "conectividad hidric",
)


# ---------------------------------------------------------------------------
# Auxiliares internos
# ---------------------------------------------------------------------------


def _iter_maps(cartography_plan: dict | None) -> list[dict]:
    """Devuelve la lista de MapSpec dicts del plan, o lista vacia."""
    if not cartography_plan:
        return []
    maps = cartography_plan.get("maps") or []
    return [m for m in maps if isinstance(m, dict)]


def _map_text(m: dict) -> str:
    """Extrae texto en minusculas de un MapSpec dict."""
    parts: list[str] = [
        m.get("map_id", ""),
        m.get("map_type", ""),
        m.get("title", ""),
        m.get("purpose", ""),
    ]
    layers = m.get("required_layers") or []
    parts.extend(layers)
    sources = m.get("source_candidates") or []
    parts.extend(sources)
    return " ".join(str(p) for p in parts).lower()


def _has_schematic_map(cartography_plan: dict | None) -> bool:
    """Devuelve True si hay algun mapa esquematico generado (estado GENERATED_PROVISIONAL)."""
    for m in _iter_maps(cartography_plan):
        status = (m.get("status") or "").lower()
        if "generated" in status or "provisional" in status:
            return True
    return False


def _has_location(phase2_data: dict | None, phase4_result: dict | None) -> bool:
    """Devuelve True si hay coordenadas disponibles en Fase 2 o Fase 4."""
    if phase2_data:
        scope = phase2_data.get("object_scope") or {}
        coords = scope.get("coordenadas_wgs84") or []
        if coords:
            return True
    if phase4_result:
        plan = phase4_result.get("cartography_plan") or {}
        center = plan.get("center") or {}
        if center.get("lat"):
            return True
        climate = phase4_result.get("climate") or {}
        if climate.get("selected_station"):
            return True
    return False


# ---------------------------------------------------------------------------
# Funciones auxiliares publicas
# ---------------------------------------------------------------------------


def extract_physical_context(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> str:
    """Extrae texto relacionado con geologia/suelos/hidrologia de los datos disponibles.

    Recorre de forma segura dicts y listas buscando menciones a:
    geologia, litologia, suelos, edafologia, hidrologia, drenaje, escorrentia,
    cauce, barranco, inundabilidad, MAP-006, capas usos_suelo/drenaje.

    Devuelve str en minusculas.
    """
    all_keywords = _GEOLOGY_KEYWORDS + _SOIL_KEYWORDS + _HYDROLOGY_KEYWORDS
    parts: list[str] = []

    def _scrape(obj: object, depth: int = 0) -> None:
        if depth > 6:
            return
        if isinstance(obj, str):
            lo = obj.lower()
            if any(kw in lo for kw in all_keywords):
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


def has_geology_source_planned(cartography_plan: dict | None = None) -> bool:
    """Devuelve True si el plan cartografico contiene fuentes o capas relacionadas con geologia.

    Detecta: geolog*, litolog*, igme, geode, base geol, riesgos geol en
    required_layers, source_candidates, title o purpose de cualquier MapSpec.
    """
    for m in _iter_maps(cartography_plan):
        text = _map_text(m)
        if any(kw in text for kw in _GEOLOGY_KEYWORDS):
            return True
    return False


def has_soil_source_planned(cartography_plan: dict | None = None) -> bool:
    """Devuelve True si el plan cartografico contiene fuentes o capas relacionadas con suelos.

    Detecta: usos_suelo, sigpac, corine, siose, edafolog*, MAP-005 en cualquier MapSpec.
    """
    for m in _iter_maps(cartography_plan):
        text = _map_text(m)
        if any(kw in text for kw in _SOIL_KEYWORDS):
            return True
    return False


def has_hydrology_source_planned(cartography_plan: dict | None = None) -> bool:
    """Devuelve True si el plan cartografico contiene fuentes o capas relacionadas con hidrologia.

    Detecta: inundab*, drenaje, hidrol*, cauce, barranco, escorrent*, snczi, MAP-006 en cualquier MapSpec.
    """
    for m in _iter_maps(cartography_plan):
        text = _map_text(m)
        if any(kw in text for kw in _HYDROLOGY_KEYWORDS):
            return True
    return False


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class PhysicalInventoryBuildResult:
    """Resultado de IV-07: FI-002 Geologia + FI-003 Suelos + FI-004 Hidrologia."""

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
        lines = ["PhysicalInventoryBuildResult:"]
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
# Constructor FI-002 Geologia
# ---------------------------------------------------------------------------


def build_geology_factor_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-002 Geologia desde datos de Fase 4 (y opcionalmente Fase 2).

    Logica:
      - Sin plan ni ubicacion: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Con plan o ubicacion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    GAP-FI-002-001: verificacion geologica oficial pendiente — siempre, MEDIA, GABINETE.
    ready_for_impact_assessment: False siempre.
    inventory_semaphore: nunca VERDE.
    """
    fid = "FI-002"
    fname = FACTOR_NAMES.get(fid, "Geologia")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_plan = bool(effective_plan)
    has_loc = _has_location(phase2_data, phase4_result)
    has_geo_source = has_geology_source_planned(effective_plan)
    has_schematic = _has_schematic_map(effective_plan)
    data_sources: list[str] = []

    if has_plan or has_loc:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        inventory_semaphore = "AMARILLO"

        if has_plan:
            data_sources.append("F4-01 — plan cartografico Fase 4 offline")
            data_sources.append("CA-10 — cartography plan")
        if has_loc:
            data_sources.append("Ubicacion del proyecto (coordenadas disponibles)")
        if has_schematic:
            data_sources.append("CA-11 — mapas esquematicos offline")

        if has_geo_source:
            description = (
                "El plan cartografico offline incluye fuentes candidatas con informacion "
                "geologica o de riesgos geologicos (IGME / mapa de riesgos geologicos). "
                "La caracterizacion geologica es preliminar de gabinete. "
                "No se dispone de consulta directa a cartografia geologica oficial (IGME/GEODE). "
                "Requiere verificacion con el Mapa Geologico de Espana u otra fuente "
                "geologica oficial aplicable antes de la redaccion del Documento Ambiental definitivo."
            )
        else:
            description = (
                "La ubicacion del proyecto esta disponible pero no consta fuente cartografica "
                "geologica especifica en el plan offline. "
                "La caracterizacion geologica es preliminar de gabinete. "
                "Requiere verificacion con cartografia geologica oficial (IGME/GEODE u "
                "equivalente autonomico) antes de la redaccion del Documento Ambiental definitivo."
            )
        if has_schematic:
            description += (
                " Los mapas esquematicos generados (CA-11) son orientativos y no "
                "sustituyen cartografia geologica oficial."
            )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de plan cartografico ni ubicacion que permitan la "
            "caracterizacion geologica preliminar del emplazamiento. "
            "Requiere plan cartografico de Fase 4 y verificacion con fuente "
            "geologica oficial (IGME/GEODE) antes del Documento Ambiental."
        )

    gap = InventoryGap(
        gap_id="GAP-FI-002-001",
        factor_id="FI-002",
        field="verificacion_geologica_oficial",
        description=(
            "Pendiente verificacion de la geologia del emplazamiento con cartografia "
            "geologica oficial. Requiere consulta al Mapa Geologico de Espana "
            "(IGME/GEODE) o equivalente autonomico. La informacion disponible en el "
            "plan cartografico offline es orientativa y no apta para el DA definitivo."
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
        gaps=[gap],
        ready_for_impact_assessment=False,
    )


# ---------------------------------------------------------------------------
# Constructor FI-003 Suelos
# ---------------------------------------------------------------------------


def build_soil_factor_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-003 Suelos desde datos de Fase 4 (y opcionalmente Fase 2).

    Logica:
      - Sin plan ni ubicacion: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Con plan o ubicacion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    GAP-FI-003-001: verificacion oficial/visual del suelo pendiente — siempre, MEDIA, CAMPO.
    ready_for_impact_assessment: False siempre.
    inventory_semaphore: nunca VERDE.
    """
    fid = "FI-003"
    fname = FACTOR_NAMES.get(fid, "Suelos")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_plan = bool(effective_plan)
    has_loc = _has_location(phase2_data, phase4_result)
    has_soil_src = has_soil_source_planned(effective_plan)
    has_schematic = _has_schematic_map(effective_plan)
    data_sources: list[str] = []

    if has_plan or has_loc:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        inventory_semaphore = "AMARILLO"

        if has_plan:
            data_sources.append("F4-01 — plan cartografico Fase 4 offline")
            data_sources.append("CA-10 — cartography plan")
        if has_loc:
            data_sources.append("Ubicacion del proyecto (coordenadas disponibles)")
        if has_schematic:
            data_sources.append("CA-11 — mapas esquematicos offline")

        if has_soil_src:
            description = (
                "El plan cartografico offline incluye el mapa de usos del suelo del entorno "
                "(MAP-005, capa usos_suelo). "
                "La caracterizacion del suelo es preliminar de gabinete basada en "
                "cartografia de usos del suelo disponible. "
                "El estado real del suelo, posibles procesos de degradacion, sellado "
                "o alteracion debe verificarse mediante inspeccion visual o fuente "
                "oficial (SIGPAC, Corine Land Cover, catastro) antes del Documento Ambiental."
            )
        else:
            description = (
                "La ubicacion del proyecto esta disponible pero no consta cartografia "
                "especifica de usos del suelo en el plan offline. "
                "La caracterizacion del suelo es preliminar de gabinete. "
                "Requiere verificacion mediante inspeccion visual o consulta a fuente "
                "oficial de usos del suelo (SIGPAC, Corine Land Cover, IGN/SIOSE) "
                "antes del Documento Ambiental definitivo."
            )
        if has_schematic:
            description += (
                " Los mapas esquematicos generados (CA-11) son orientativos y no "
                "sustituyen fuente edafologica oficial."
            )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de plan cartografico ni ubicacion que permitan la "
            "caracterizacion preliminar del suelo del emplazamiento. "
            "Requiere plan cartografico con capa de usos del suelo e inspeccion "
            "visual o fuente oficial antes del Documento Ambiental."
        )

    gap = InventoryGap(
        gap_id="GAP-FI-003-001",
        factor_id="FI-003",
        field="verificacion_estado_uso_suelo",
        description=(
            "Pendiente verificacion del estado y uso real del suelo en el emplazamiento "
            "y su entorno. Requiere inspeccion visual o consulta a fuente oficial "
            "(SIGPAC / Corine Land Cover / IGN SIOSE). "
            "La cartografia de usos del suelo offline no acredita el estado real, "
            "posibles procesos de sellado, degradacion o contaminacion del suelo."
        ),
        criticality="MEDIA",
        resolution_mode="CAMPO",
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
# Constructor FI-004 Hidrologia
# ---------------------------------------------------------------------------


def build_hydrology_factor_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-004 Hidrologia desde datos de Fase 4 (y opcionalmente Fase 2).

    Logica:
      - Sin plan ni ubicacion: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Con plan o ubicacion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    GAP-FI-004-001:
      - criticality ALTA si hay relacion con inundabilidad (MAP-006 o capa drenaje/inundab).
      - criticality MEDIA en otro caso.
    resolution_mode: GABINETE siempre.
    ready_for_impact_assessment: False siempre.
    inventory_semaphore: nunca VERDE.
    """
    fid = "FI-004"
    fname = FACTOR_NAMES.get(fid, "Hidrologia")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_plan = bool(effective_plan)
    has_loc = _has_location(phase2_data, phase4_result)
    has_hydro_src = has_hydrology_source_planned(effective_plan)
    has_schematic = _has_schematic_map(effective_plan)
    data_sources: list[str] = []

    # La criticidad del gap sube a ALTA si hay relacion con inundabilidad
    gap_criticality = "ALTA" if has_hydro_src else "MEDIA"

    if has_plan or has_loc:
        evidence_status = "ESTIMADO"
        field_mode = "CAMPO_RECOMENDADO"
        inventory_semaphore = "AMARILLO"

        if has_plan:
            data_sources.append("F4-01 — plan cartografico Fase 4 offline")
            data_sources.append("CA-10 — cartography plan")
        if has_loc:
            data_sources.append("Ubicacion del proyecto (coordenadas disponibles)")
        if has_schematic:
            data_sources.append("CA-11 — mapas esquematicos offline")

        if has_hydro_src:
            description = (
                "El plan cartografico offline incluye el mapa de inundabilidad y drenaje "
                "(MAP-006, capas inundabilidad y drenaje). "
                "La evaluacion hidrologica es preliminar de gabinete. "
                "La red de drenaje, escorrentia y posibles cauces o barrancos del entorno "
                "deben verificarse con fuente hidrologica oficial (SNCZI, IGME, Grafcan "
                "RIESGOMAP u organismo de cuenca competente) antes del Documento Ambiental definitivo. "
                "La evaluacion offline no permite determinar la conectividad hidrica ni "
                "la relacion del proyecto con la red de drenaje real."
            )
        else:
            description = (
                "La ubicacion del proyecto esta disponible pero no consta cartografia "
                "especifica de drenaje o inundabilidad en el plan offline. "
                "La evaluacion hidrologica es preliminar de gabinete. "
                "La red de drenaje, cauces, barrancos y escorrentia del entorno deben "
                "verificarse con fuente hidrologica oficial antes del Documento Ambiental definitivo."
            )
        if has_schematic:
            description += (
                " Los mapas esquematicos generados (CA-11) son orientativos y no "
                "sustituyen cartografia hidrologica oficial."
            )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de plan cartografico ni ubicacion que permitan la "
            "evaluacion hidrologica preliminar del emplazamiento. "
            "Requiere plan cartografico con capas de drenaje/inundabilidad y "
            "verificacion con fuente hidrologica oficial antes del Documento Ambiental."
        )

    gap = InventoryGap(
        gap_id="GAP-FI-004-001",
        factor_id="FI-004",
        field="verificacion_hidrologica_oficial",
        description=(
            "Pendiente verificacion de la red hidrologica, drenaje y escorrentia "
            "en el entorno del emplazamiento con fuente oficial. Requiere consulta al "
            "SNCZI (Sistema Nacional de Cartografia de Zonas Inundables), al organismo "
            "de cuenca competente o a Grafcan RIESGOMAP en Canarias. "
            "La cartografia offline no permite descartar la presencia de cauces, "
            "barrancos ni conectividad hidrica."
        ),
        criticality=gap_criticality,
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


def build_physical_inventory_factors_from_phase4(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> PhysicalInventoryBuildResult:
    """Construye FI-002, FI-003 y FI-004 y los devuelve como PhysicalInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    fi002 = build_geology_factor_from_phase4(phase2_data, phase4_result, cartography_plan)
    fi003 = build_soil_factor_from_phase4(phase2_data, phase4_result, cartography_plan)
    fi004 = build_hydrology_factor_from_phase4(phase2_data, phase4_result, cartography_plan)

    for fi, label in [(fi002, "FI-002 Geologia"), (fi003, "FI-003 Suelos"), (fi004, "FI-004 Hidrologia")]:
        if fi.evidence_status == "PENDIENTE":
            warnings.append(
                f"{label}: sin plan cartografico ni ubicacion disponibles. "
                "Pendiente caracterizacion de Fase 4."
            )

    has_geo = has_geology_source_planned(
        cartography_plan if cartography_plan is not None
        else (phase4_result or {}).get("cartography_plan")
    )
    has_hydro = has_hydrology_source_planned(
        cartography_plan if cartography_plan is not None
        else (phase4_result or {}).get("cartography_plan")
    )

    notes.append(
        f"IV-07: FI-002={fi002.evidence_status}/{fi002.inventory_semaphore}, "
        f"FI-003={fi003.evidence_status}/{fi003.inventory_semaphore}, "
        f"FI-004={fi004.evidence_status}/{fi004.inventory_semaphore}. "
        f"Fuente geologica: {has_geo}. Fuente hidrologica: {has_hydro}. "
        "Verificacion oficial pendiente en los tres factores."
    )

    return PhysicalInventoryBuildResult(
        factors=[fi002, fi003, fi004],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_physical_factors_into_summary(
    summary: InventorySummary,
    physical_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-002, FI-003 y/o FI-004 en un InventorySummary sin mutar el original.

    Preserva el orden canonico de FACTOR_NAMES.
    Propaga warnings y notes del summary original.
    """
    merged_map = {f.factor_id: f for f in summary.factors}
    for pf in physical_factors:
        merged_map[pf.factor_id] = pf

    merged_factors = [merged_map[fid] for fid in sorted(FACTOR_NAMES.keys()) if fid in merged_map]

    new_summary = build_inventory_summary(summary.expediente_id, merged_factors)
    new_summary.warnings = list(summary.warnings)
    new_summary.notes = list(summary.notes)
    return new_summary
