"""
inventory_biodiversity_builder -- IV-10
Constructor de factores FI-007 Flora y FI-008 Fauna desde Fase 2/Fase 4 offline.

Integra la ubicacion del proyecto, el plan cartografico offline y la documentacion
del promotor para construir FI-007 y FI-008 con:
  - deteccion de menciones botanicas/faunisticas en la documentacion disponible;
  - contexto de Red Natura 2000 / ENP / usos del suelo si consta en el plan;
  - gaps de consulta oficial y/o prospeccion de campo obligatorios.

Reglas de prudencia (no negociables):
  - No se afirma "no hay flora", "sin vegetacion", "sin habitats", "sin especies protegidas".
  - No se afirma "no hay fauna", "sin fauna", "sin aves", "sin nidificacion".
  - No se descarta afeccion a flora ni fauna sin prospeccion oficial.
  - No se sustituye la prospeccion botanica ni faunistica de campo.
  - No se sustituye la consulta a fuentes oficiales de biodiversidad.
  - ready_for_impact_assessment: False por defecto en modo offline.
  - inventory_semaphore: nunca VERDE sin prospeccion/fuente oficial documentada.
  - No se usan terminos de valoracion: COMPATIBLE, MODERADO, SEVERO, CRITICO.

No consulta bancos de biodiversidad (GBIF, MITECO, IDE ambiental).
No consulta WMS/WMTS.
No verifica especies protegidas.
No realiza prospeccion de campo.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) -- FactorInventory, InventoryGap, InventorySummary
  IV-06 (inventory_protected_areas_builder) -- contexto Red Natura/ENP (opcional)
  F4-01 (phase4_offline_pipeline) -- estructura phase4_result.json
  CA-10 (cartography_plan) -- plan cartografico offline
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

_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "flora",
    "vegetaci",
    "habitat",
    "especie",
    "fauna",
    "avifauna",
    "aves",
    "reptil",
    "mamifer",
    "quiropter",
    "biodiversidad",
    "red natura",
    "zec",
    "lic",
    "zepa",
    "enp",
    "espacios protegidos",
    "suelo urbano",
    "poligono industrial",
    "polígono industrial",
    "entorno antropizado",
    "parcela",
    "nave",
    "taller",
    "matorral",
    "arbolado",
    "palmera",
    "nidificaci",
    "murcielago",
    "murciélago",
)

_FLORA_TERMS: tuple[str, ...] = (
    "flora",
    "vegetaci",
    "habitat",
    "especie vegetal",
    "vegetacion natural",
    "vegetación natural",
    "matorral",
    "arbolado",
    "palmera",
    "especie protegida",
    "biodiversidad",
)

_FAUNA_TERMS: tuple[str, ...] = (
    "fauna",
    "avifauna",
    "aves",
    "reptil",
    "mamifer",
    "quiropter",
    "murcielago",
    "murciélago",
    "especie protegida",
    "nidificaci",
    "biodiversidad",
)

_BIO_MAP_TYPES: frozenset[str] = frozenset({"red_natura_enp", "usos_suelo"})
_BIO_MAP_IDS: frozenset[str] = frozenset({"MAP-004", "MAP-005"})
_BIO_LAYERS: frozenset[str] = frozenset({
    "red_natura_2000",
    "espacios_naturales_protegidos",
    "usos_suelo",
})
_BIO_PLAN_KEYWORDS: tuple[str, ...] = (
    "red natura",
    "natura 2000",
    "enp",
    "zepa",
    "zec",
    "lic",
    "usos_suelo",
    "biodiversidad",
)


# ---------------------------------------------------------------------------
# Funciones auxiliares privadas
# ---------------------------------------------------------------------------


def _has_location(
    phase2_data: dict | None,
    phase4_result: dict | None,
    cartography_plan: dict | None = None,
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
    if cartography_plan:
        center = (cartography_plan.get("center") or {})
        if center.get("lat") is not None:
            return True
    return False


def _extract_phase2_text(phase2_data: dict | None) -> str:
    """Extrae texto de actividad de phase2_data en minusculas."""
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


def extract_biodiversity_context(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> str:
    """Extrae texto relacionado con biodiversidad de los datos disponibles.

    Recorre de forma segura dicts y listas buscando menciones a:
    flora, vegetacion, habitat, especie, fauna, avifauna, aves, reptil,
    mamiferos, quiropteros, biodiversidad, Red Natura, ZEC, LIC, ZEPA,
    ENP, espacios protegidos, poligono industrial, entorno antropizado, etc.

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


def detect_flora_mentions(text: str) -> list[str]:
    """Detecta terminos de flora, vegetacion y habitats en texto disponible.

    Devuelve lista sin duplicados en orden de aparicion.
    No interpreta mas alla de presencia textual.
    """
    found: list[str] = []
    lo = text.lower()
    for term in _FLORA_TERMS:
        if term in lo and term not in found:
            found.append(term)
    return found


def detect_fauna_mentions(text: str) -> list[str]:
    """Detecta terminos de fauna, aves, reptiles y nidificacion en texto.

    Devuelve lista sin duplicados en orden de aparicion.
    No interpreta mas alla de presencia textual.
    """
    found: list[str] = []
    lo = text.lower()
    for term in _FAUNA_TERMS:
        if term in lo and term not in found:
            found.append(term)
    return found


def has_biodiversity_related_context(
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> bool:
    """Devuelve True si detecta contexto de biodiversidad relevante.

    Detecta: Red Natura, ENP, MAP-004, MAP-005, usos_suelo, capas de
    red_natura_2000, espacios_naturales_protegidos en el plan cartografico.
    """
    plans: list[dict] = []
    if phase4_result:
        embedded = phase4_result.get("cartography_plan")
        if embedded and isinstance(embedded, dict):
            plans.append(embedded)
    if cartography_plan and isinstance(cartography_plan, dict):
        plans.append(cartography_plan)

    for plan in plans:
        maps = plan.get("maps") or []
        for m in maps:
            if not isinstance(m, dict):
                continue
            if m.get("map_type") in _BIO_MAP_TYPES:
                return True
            if m.get("map_id") in _BIO_MAP_IDS:
                return True
            layers = m.get("required_layers") or []
            if any(lay in _BIO_LAYERS for lay in layers):
                return True
            for v in m.values():
                if isinstance(v, str) and any(kw in v.lower() for kw in _BIO_PLAN_KEYWORDS):
                    return True

    return False


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class BiodiversityInventoryBuildResult:
    """Resultado de IV-10: FI-007 Flora y FI-008 Fauna."""

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
        lines = ["BiodiversityInventoryBuildResult:"]
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
# Constructor FI-007 Flora
# ---------------------------------------------------------------------------


def build_flora_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-007 Flora desde datos de Fase 2 y Fase 4.

    Fuentes usadas:
      - phase2_data.object_scope: descripcion de actividad y operaciones.
      - phase4_result: plan cartografico, datos de ubicacion, contexto ENP/Red Natura.
      - cartography_plan: plan cartografico explícito.

    Logica de evidencia:
      - DECLARADO si el promotor menciona flora/vegetacion/habitats de forma concreta.
      - ESTIMADO si hay ubicacion, cartografia offline o contexto ENP/Red Natura/usos_suelo.
      - PENDIENTE si no hay informacion util.

    Logica de semaforo:
      - ROJO_AMARILLO si hay menciones a flora/habitats/especies sin resolver.
      - AMARILLO si hay ubicacion/cartografia sin menciones explícitas.
      - NO_CONSTA si no hay datos.
      - Nunca VERDE sin prospeccion/fuente oficial documentada.

    Logica de field_mode:
      - CAMPO_NECESARIO si hay menciones a habitats/vegetacion natural/especie protegida.
      - CAMPO_RECOMENDADO si solo hay ubicacion/cartografia offline.
      - NO_CONSTA si sin ubicacion ni contexto.

    GAP-FI-007-001: consulta/prospeccion de flora y habitats pendiente.
      Criticidad ALTA si Red Natura/ENP o menciones; MEDIA en caso general.
      Resolucion CAMPO si prospeccion necesaria; GABINETE si solo consulta oficial.
    GAP-FI-007-002: aclaracion de mencion botanica/habitat detectada.
      ALTA / CAMPO. Solo si hay menciones.
    ready_for_impact_assessment: False por defecto.
    """
    fid = "FI-007"
    fname = FACTOR_NAMES.get(fid, "Flora")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_loc = _has_location(phase2_data, phase4_result, effective_plan)
    has_bio_ctx = has_biodiversity_related_context(phase4_result, effective_plan)
    activity_text = _extract_phase2_text(phase2_data)
    all_context = extract_biodiversity_context(phase2_data, phase4_result, effective_plan)

    promoter_flora_mentions = detect_flora_mentions(activity_text)
    all_flora_mentions = detect_flora_mentions(all_context)

    has_promoter_decl = bool(promoter_flora_mentions)
    has_any_mention = bool(all_flora_mentions)

    # --- Evidence status ---
    if has_promoter_decl:
        evidence_status = "DECLARADO"
    elif has_loc or has_bio_ctx or has_any_mention:
        evidence_status = "ESTIMADO"
    else:
        evidence_status = "PENDIENTE"

    # --- Field mode ---
    if has_any_mention:
        field_mode = "CAMPO_NECESARIO"
    elif has_loc or has_bio_ctx:
        field_mode = "CAMPO_RECOMENDADO"
    else:
        field_mode = "NO_CONSTA"

    # --- Semaphore ---
    if evidence_status == "PENDIENTE":
        inventory_semaphore = "NO_CONSTA"
    elif has_any_mention:
        inventory_semaphore = "ROJO_AMARILLO"
    elif has_loc or has_bio_ctx:
        inventory_semaphore = "AMARILLO"
    else:
        inventory_semaphore = "NO_CONSTA"

    # --- Data sources ---
    data_sources: list[str] = []
    if phase2_data:
        data_sources.append("OB-06 — documentacion del promotor (Fase 2)")
    if phase4_result:
        data_sources.append("F4-01 — plan de Fase 4 offline")
    if effective_plan:
        data_sources.append("CA-10 — plan cartografico offline")

    # --- Description ---
    desc_parts: list[str] = []

    desc_parts.append(
        "Caracterizacion preliminar de gabinete de FI-007 Flora. "
        "No se ha realizado prospeccion botanica ni consulta a fuentes "
        "oficiales de biodiversidad (IDE ambiental, bancos de datos "
        "de biodiversidad, organismos competentes)."
    )

    if has_loc:
        desc_parts.append(
            "Se dispone de referencia de ubicacion del proyecto. "
            "La caracterizacion definitiva de la vegetacion y habitats presentes "
            "requiere prospeccion botanica de campo y consulta al inventario "
            "de habitats de interes comunitario y a la cartografia de vegetacion "
            "de la comunidad autonoma correspondiente."
        )
    else:
        desc_parts.append(
            "No se dispone de coordenadas ni referencia de ubicacion suficiente. "
            "La ubicacion es indispensable antes de cualquier caracterizacion "
            "de flora y habitats."
        )

    if has_bio_ctx:
        desc_parts.append(
            "El plan cartografico incluye informacion relacionada con Red Natura 2000, "
            "Espacios Naturales Protegidos y/o usos del suelo. "
            "Este contexto incrementa la relevancia de la prospeccion botanica "
            "y la consulta al organo ambiental competente."
        )

    if has_any_mention:
        terms_str = ", ".join(all_flora_mentions[:6])
        if len(all_flora_mentions) > 6:
            terms_str += "..."
        desc_parts.append(
            f"Se detectan menciones relacionadas con flora o habitats en la "
            f"documentacion disponible: {terms_str}. "
            "Estas menciones no constituyen caracterizacion de la flora presente "
            "y requieren verificacion mediante prospeccion y/o fuente oficial."
        )

    desc_parts.append(
        "No es posible afirmar ausencia de flora protegida, habitats de interes "
        "comunitario o vegetacion natural relevante en el ambito del proyecto "
        "sin prospeccion botanica de campo o consulta a fuentes de biodiversidad "
        "oficiales. Esta caracterizacion es de caracter preliminar."
    )

    description = " ".join(desc_parts)

    # --- Gaps ---
    gap_criticality = "ALTA" if (has_bio_ctx or has_any_mention) else "MEDIA"
    gap_resolution = "CAMPO" if (has_bio_ctx or has_any_mention or has_loc) else "GABINETE"

    gap_main = InventoryGap(
        gap_id="GAP-FI-007-001",
        factor_id="FI-007",
        field="prospeccion_flora_habitats",
        description=(
            "Pendiente prospeccion botanica de campo y/o consulta a fuentes "
            "oficiales de biodiversidad para caracterizar la vegetacion, "
            "habitats y flora presente en el ambito del proyecto. "
            "Se requiere verificar la presencia de habitats de interes "
            "comunitario (Directiva 92/43/CEE), flora protegida autonómica "
            "y/o nacional, y especies incluidas en el Catalogo Español de "
            "Especies Amenazadas."
        ),
        criticality=gap_criticality,
        resolution_mode=gap_resolution,
        status="PENDIENTE",
    )

    gaps = [gap_main]

    if has_any_mention:
        terms_gap = ", ".join(all_flora_mentions[:4])
        gap_clarification = InventoryGap(
            gap_id="GAP-FI-007-002",
            factor_id="FI-007",
            field="aclaracion_menciones_flora_habitats",
            description=(
                f"Se han detectado menciones a: {terms_gap} en la documentacion "
                "disponible. Es necesario aclarar el alcance de estas menciones "
                "mediante prospeccion botanica y/o consulta al organo ambiental "
                "competente antes de caracterizar el factor flora."
            ),
            criticality="ALTA",
            resolution_mode="CAMPO",
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
# Constructor FI-008 Fauna
# ---------------------------------------------------------------------------


def build_fauna_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> FactorInventory:
    """Construye FI-008 Fauna desde datos de Fase 2 y Fase 4.

    Fuentes usadas:
      - phase2_data.object_scope: descripcion de actividad y operaciones.
      - phase4_result: plan cartografico, datos de ubicacion, contexto ENP/Red Natura.
      - cartography_plan: plan cartografico explícito.

    Logica de evidencia:
      - DECLARADO si el promotor menciona fauna/aves/reptiles/etc. de forma concreta.
      - ESTIMADO si hay ubicacion, cartografia offline o contexto ENP/Red Natura/usos_suelo.
      - PENDIENTE si no hay informacion util.

    Logica de semaforo:
      - ROJO_AMARILLO si hay menciones a fauna/especies/nidificacion sin resolver.
      - AMARILLO si hay ubicacion/cartografia sin menciones explícitas.
      - NO_CONSTA si no hay datos.
      - Nunca VERDE sin prospeccion/fuente oficial documentada.

    Logica de field_mode:
      - CAMPO_NECESARIO si hay menciones a fauna/nidificacion/especie protegida.
      - CAMPO_RECOMENDADO si solo hay ubicacion/cartografia offline.
      - NO_CONSTA si sin ubicacion ni contexto.

    GAP-FI-008-001: consulta/prospeccion de fauna pendiente.
      Criticidad ALTA si Red Natura/ENP o menciones; MEDIA en caso general.
      Resolucion CAMPO si prospeccion necesaria; GABINETE si solo consulta oficial.
    GAP-FI-008-002: aclaracion de mencion faunistica detectada.
      ALTA / CAMPO. Solo si hay menciones.
    ready_for_impact_assessment: False por defecto.
    """
    fid = "FI-008"
    fname = FACTOR_NAMES.get(fid, "Fauna")

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    has_loc = _has_location(phase2_data, phase4_result, effective_plan)
    has_bio_ctx = has_biodiversity_related_context(phase4_result, effective_plan)
    activity_text = _extract_phase2_text(phase2_data)
    all_context = extract_biodiversity_context(phase2_data, phase4_result, effective_plan)

    promoter_fauna_mentions = detect_fauna_mentions(activity_text)
    all_fauna_mentions = detect_fauna_mentions(all_context)

    has_promoter_decl = bool(promoter_fauna_mentions)
    has_any_mention = bool(all_fauna_mentions)

    # --- Evidence status ---
    if has_promoter_decl:
        evidence_status = "DECLARADO"
    elif has_loc or has_bio_ctx or has_any_mention:
        evidence_status = "ESTIMADO"
    else:
        evidence_status = "PENDIENTE"

    # --- Field mode ---
    if has_any_mention:
        field_mode = "CAMPO_NECESARIO"
    elif has_loc or has_bio_ctx:
        field_mode = "CAMPO_RECOMENDADO"
    else:
        field_mode = "NO_CONSTA"

    # --- Semaphore ---
    if evidence_status == "PENDIENTE":
        inventory_semaphore = "NO_CONSTA"
    elif has_any_mention:
        inventory_semaphore = "ROJO_AMARILLO"
    elif has_loc or has_bio_ctx:
        inventory_semaphore = "AMARILLO"
    else:
        inventory_semaphore = "NO_CONSTA"

    # --- Data sources ---
    data_sources: list[str] = []
    if phase2_data:
        data_sources.append("OB-06 — documentacion del promotor (Fase 2)")
    if phase4_result:
        data_sources.append("F4-01 — plan de Fase 4 offline")
    if effective_plan:
        data_sources.append("CA-10 — plan cartografico offline")

    # --- Description ---
    desc_parts: list[str] = []

    desc_parts.append(
        "Caracterizacion preliminar de gabinete de FI-008 Fauna. "
        "No se ha realizado prospeccion faunistica ni consulta a fuentes "
        "oficiales de biodiversidad (IDE ambiental, bancos de datos "
        "de biodiversidad, organismos competentes)."
    )

    if has_loc:
        desc_parts.append(
            "Se dispone de referencia de ubicacion del proyecto. "
            "La caracterizacion definitiva de la fauna requiere prospeccion "
            "de campo especifica (aves, reptiles, mamiferos, quiropteros) "
            "y consulta al Catalogo Español de Especies Amenazadas y "
            "a los catalogos autonómicos de especies protegidas."
        )
    else:
        desc_parts.append(
            "No se dispone de coordenadas ni referencia de ubicacion suficiente. "
            "La ubicacion es indispensable antes de cualquier caracterizacion "
            "faunistica del emplazamiento."
        )

    if has_bio_ctx:
        desc_parts.append(
            "El plan cartografico incluye informacion relacionada con Red Natura 2000, "
            "Espacios Naturales Protegidos y/o usos del suelo. "
            "Este contexto incrementa la relevancia de la prospeccion faunistica "
            "y la consulta al organo ambiental competente sobre especies presentes."
        )

    if has_any_mention:
        terms_str = ", ".join(all_fauna_mentions[:6])
        if len(all_fauna_mentions) > 6:
            terms_str += "..."
        desc_parts.append(
            f"Se detectan menciones relacionadas con fauna en la documentacion "
            f"disponible: {terms_str}. "
            "Estas menciones no constituyen caracterizacion de la fauna presente "
            "y requieren verificacion mediante prospeccion y/o fuente oficial."
        )

    desc_parts.append(
        "No es posible afirmar ausencia de especies protegidas, nidificacion "
        "o fauna sensible en el ambito del proyecto sin prospeccion faunistica "
        "de campo o consulta a fuentes de biodiversidad oficiales. "
        "Esta caracterizacion es de caracter preliminar."
    )

    description = " ".join(desc_parts)

    # --- Gaps ---
    gap_criticality = "ALTA" if (has_bio_ctx or has_any_mention) else "MEDIA"
    gap_resolution = "CAMPO" if (has_bio_ctx or has_any_mention or has_loc) else "GABINETE"

    gap_main = InventoryGap(
        gap_id="GAP-FI-008-001",
        factor_id="FI-008",
        field="prospeccion_fauna",
        description=(
            "Pendiente prospeccion faunistica de campo y/o consulta a fuentes "
            "oficiales de biodiversidad para caracterizar la fauna presente en "
            "el ambito del proyecto. "
            "Se requiere verificar la presencia de especies incluidas en el "
            "Catalogo Español de Especies Amenazadas, catalogos autonómicos, "
            "Directiva 2009/147/CE (Aves) y Directiva 92/43/CEE (Habitats). "
            "Se debe prestar especial atencion a aves, reptiles, mamiferos y "
            "quiropteros presentes en el area de influencia."
        ),
        criticality=gap_criticality,
        resolution_mode=gap_resolution,
        status="PENDIENTE",
    )

    gaps = [gap_main]

    if has_any_mention:
        terms_gap = ", ".join(all_fauna_mentions[:4])
        gap_clarification = InventoryGap(
            gap_id="GAP-FI-008-002",
            factor_id="FI-008",
            field="aclaracion_menciones_faunisticas",
            description=(
                f"Se han detectado menciones a: {terms_gap} en la documentacion "
                "disponible. Es necesario aclarar el alcance de estas menciones "
                "mediante prospeccion faunistica y/o consulta al organo ambiental "
                "competente antes de caracterizar el factor fauna."
            ),
            criticality="ALTA",
            resolution_mode="CAMPO",
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
# Constructor combinado
# ---------------------------------------------------------------------------


def build_biodiversity_inventory_factors_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
    cartography_plan: dict | None = None,
) -> BiodiversityInventoryBuildResult:
    """Construye FI-007 y FI-008 y los devuelve como BiodiversityInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    effective_plan = cartography_plan
    if effective_plan is None and phase4_result:
        effective_plan = phase4_result.get("cartography_plan")

    fi007 = build_flora_factor_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_plan,
    )
    fi008 = build_fauna_factor_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_plan,
    )

    if fi007.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-007 Flora: sin ubicacion ni documentacion del promotor. "
            "No es posible iniciar la caracterizacion de flora y habitats."
        )
    if fi008.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-008 Fauna: sin ubicacion ni documentacion del promotor. "
            "No es posible iniciar la caracterizacion faunistica."
        )

    if fi007.inventory_semaphore == "ROJO_AMARILLO":
        warnings.append(
            "FI-007 Flora: menciones a flora/habitats/especies detectadas en la "
            "documentacion sin resolver. Prospeccion botanica necesaria."
        )
    if fi008.inventory_semaphore == "ROJO_AMARILLO":
        warnings.append(
            "FI-008 Fauna: menciones a fauna/especies/nidificacion detectadas en la "
            "documentacion sin resolver. Prospeccion faunistica necesaria."
        )

    has_bio_ctx = has_biodiversity_related_context(phase4_result, effective_plan)
    if has_bio_ctx:
        notes.append(
            "IV-10: contexto de Red Natura/ENP/usos_suelo detectado en el plan "
            "cartografico. FI-007 y FI-008 tienen gap ALTA."
        )

    notes.append(
        f"IV-10: FI-007={fi007.evidence_status}/{fi007.inventory_semaphore} "
        f"FI-008={fi008.evidence_status}/{fi008.inventory_semaphore}. "
        "Prospeccion de campo pendiente en ambos factores."
    )

    return BiodiversityInventoryBuildResult(
        factors=[fi007, fi008],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_biodiversity_factors_into_summary(
    summary: InventorySummary,
    biodiversity_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-007 y FI-008 en un InventorySummary sin mutar el original.

    Preserva el orden canonico de FACTOR_NAMES.
    Propaga warnings y notes del summary original.
    """
    merged_map = {f.factor_id: f for f in summary.factors}
    for fac in biodiversity_factors:
        merged_map[fac.factor_id] = fac

    merged_factors = [merged_map[fid] for fid in sorted(FACTOR_NAMES.keys()) if fid in merged_map]

    new_summary = build_inventory_summary(summary.expediente_id, merged_factors)
    new_summary.warnings = list(summary.warnings)
    new_summary.notes = list(summary.notes)
    return new_summary
