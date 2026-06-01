"""
inventory_builder -- IV-02
Constructor de inventario ambiental desde Fase 4 offline.

Lee los outputs de Fase 4 (phase4_result.json, phase4_climate_result.json,
cartografia_plan.json) y construye el InventorySummary inicial de Fase 5
con los 16 factores FI-001...FI-016.

FI-001 Clima se construye con datos reales del pipeline CL-06.
Los demás factores (FI-002...FI-016) se inicializan en estado base
PENDIENTE/NO_CONSTA con un gap de inventario pendiente.

No consulta fuentes externas.
No inventa datos.
No valora impactos.
No genera Fase 6.
No usa IA.

Depende de:
- IV-00: inventory_model.py
- IV-01: inventory_renderer.py
- F4-01: phase4_offline_pipeline.py (outputs JSON)
- CL-06: phase4_climate_pipeline.py (outputs JSON)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eia_agent.core.inventory_model import (
    FACTOR_NAMES,
    FactorInventory,
    InventoryGap,
    InventorySummary,
    build_inventory_summary,
    classify_semaphore_from_evidence,
)
from eia_agent.core.inventory_renderer import write_inventory_markdown_files
from eia_agent.core.inventory_risk_builder import (
    build_risk_inventory_factors_from_phase4,
    merge_risk_factors_into_summary,
)
from eia_agent.core.inventory_context_builder import (
    build_context_inventory_factors_from_phase_data,
    merge_context_factors_into_summary,
)
from eia_agent.core.inventory_pressure_builder import (
    build_pressure_inventory_factors_from_phase_data,
    merge_pressure_factors_into_summary,
)
from eia_agent.core.inventory_protected_areas_builder import (
    build_protected_areas_inventory_factors_from_phase4,
    merge_protected_area_factors_into_summary,
)
from eia_agent.core.inventory_physical_builder import (
    build_physical_inventory_factors_from_phase4,
    merge_physical_factors_into_summary,
)
from eia_agent.core.inventory_climate_change_builder import (
    build_climate_change_inventory_factor_from_phase4,
    merge_climate_change_factor_into_summary,
)
from eia_agent.core.inventory_heritage_builder import (
    build_heritage_inventory_factor_from_phase4,
    merge_heritage_factor_into_summary,
)
from eia_agent.core.inventory_biodiversity_builder import (
    build_biodiversity_inventory_factors_from_phase_data,
    merge_biodiversity_factors_into_summary,
)


# ---------------------------------------------------------------------------
# load_json_file
# ---------------------------------------------------------------------------

def load_json_file(path: "str | Path") -> dict:
    """Carga un archivo JSON local.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si el contenido no es JSON valido.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido en {p}: {exc}") from exc


# ---------------------------------------------------------------------------
# InventoryBuildResult
# ---------------------------------------------------------------------------

@dataclass
class InventoryBuildResult:
    """Resultado del constructor de inventario ambiental desde Fase 4."""

    expediente_id: str
    inventory_summary: InventorySummary
    factor_count: int
    ready_count: int
    rendered_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "factor_count": self.factor_count,
            "ready_count": self.ready_count,
            "all_ready_for_phase6": self.inventory_summary.all_ready_for_phase6,
            "rendered_files": list(self.rendered_files),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Inventario Fase 5 -- {self.expediente_id}",
            f"  Factores        : {self.factor_count}/16",
            f"  Listos Fase 6   : {self.ready_count}/{self.factor_count}",
            f"  Listo Fase 6    : {'SI' if self.inventory_summary.all_ready_for_phase6 else 'NO'}",
        ]
        if self.rendered_files:
            lines.append(f"  Archivos escritos: {len(self.rendered_files)}")
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  NOTA: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_climate_factor_from_phase4
# ---------------------------------------------------------------------------

def build_climate_factor_from_phase4(climate_data: dict) -> FactorInventory:
    """Construye FI-001 Clima desde el dict de phase4_climate_result.

    Args:
        climate_data: dict con la estructura de Phase4ClimateResult.to_dict().
                      Claves relevantes:
                        - selected_station: dict con station_id y name
                        - station_distance_km: float
                        - station_selection_status: OPTIMA/ACEPTABLE/LEJANA/NO_DISPONIBLE
                        - climate_classification: dict con koppen_code, martonne_index, etc.
                        - warnings/notes: listas de str

    Returns:
        FactorInventory para FI-001 Clima con evidence_status, field_mode,
        description, data_sources, gaps y semaforo derivados de los datos reales.
    """
    station = climate_data.get("selected_station")
    station_name = station.get("name", "Desconocida") if station else None
    station_id = station.get("station_id", "?") if station else None
    distance_km = climate_data.get("station_distance_km")
    sel_status = climate_data.get("station_selection_status", "NO_DISPONIBLE")

    cc = climate_data.get("climate_classification")
    has_station = station is not None
    has_classification = bool(cc and cc.get("koppen_code"))

    warnings: list[str] = []
    notes: list[str] = []

    # Determinar nivel de evidencia
    if has_station and has_classification:
        evidence_status = "CONFIRMADO_GABINETE"
        field_mode = "GABINETE_SUFICIENTE"
        ready = True
    elif has_station:
        evidence_status = "DECLARADO"
        field_mode = "GABINETE_SUFICIENTE"
        ready = False
        warnings.append(
            "Estacion seleccionada pero sin clasificacion climatica completa. "
            "No se ha podido determinar Koppen ni Martonne."
        )
    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        ready = False
        warnings.append(
            "No se ha podido seleccionar una estacion climatica. "
            "Factor FI-001 Clima no caracterizado."
        )

    # Aviso si estacion lejana
    if sel_status == "LEJANA" and has_station:
        dist_str = f"{distance_km:.1f} km" if distance_km is not None else "desconocida"
        warnings.append(
            f"Estacion climatica LEJANA: '{station_name}' a {dist_str} (>25 km). "
            "Los datos pueden no ser representativos de la ubicacion del expediente. "
            "Valorar estacion alternativa o realizacion de prospeccion de campo."
        )
    elif sel_status == "NO_DISPONIBLE":
        warnings.append("No hay estaciones disponibles en el area del expediente.")

    # Propagar warnings del pipeline (sin duplicar)
    for w in climate_data.get("warnings", []):
        if w not in warnings:
            warnings.append(w)

    # Data sources
    data_sources: list[str] = ["CL-06 -- Pipeline climatico Fase 4 offline"]
    if has_station:
        dist_label = f"{distance_km:.1f} km" if distance_km is not None else "dist. desconocida"
        data_sources.append(
            f"Estacion AEMET: {station_name} ({station_id}) -- {dist_label} [{sel_status}]"
        )
    if has_classification:
        data_sources.append("Normales climatologicas AEMET")

    # Description
    parts: list[str] = [
        "Datos climaticos obtenidos mediante el pipeline Fase 4 offline (CL-06)."
    ]
    if has_station:
        dist_label = f"{distance_km:.1f} km" if distance_km is not None else "distancia desconocida"
        parts.append(
            f"Estacion seleccionada: {station_name} ({station_id}) "
            f"a {dist_label} [{sel_status}]."
        )
    if has_classification:
        t = cc.get("annual_temperature_c")
        p_val = cc.get("annual_precipitation_mm")
        koppen_code = cc.get("koppen_code", "?")
        koppen_label = cc.get("koppen_label", "?")
        martonne_idx = cc.get("martonne_index")
        martonne_label = cc.get("martonne_label", "?")
        dry_names = cc.get("dry_months_names", [])

        if t is not None:
            parts.append(f"Temperatura media anual: {t:.1f} C.")
        if p_val is not None:
            parts.append(f"Precipitacion media anual: {p_val:.1f} mm.")
        parts.append(f"Clasificacion de Koppen-Geiger: {koppen_code} ({koppen_label}).")
        if martonne_idx is not None:
            parts.append(f"Indice de Martonne: {martonne_idx:.1f} mm/C ({martonne_label}).")
        if dry_names:
            if len(dry_names) == 12:
                parts.append("Meses secos (Gaussen): todos los meses del ano.")
            else:
                parts.append(f"Meses secos (Gaussen): {', '.join(dry_names)}.")
    else:
        parts.append(
            "No se dispone de clasificacion climatica completa. "
            "Consultar fuentes directas de AEMET."
        )

    description = " ".join(parts)

    # Notes
    notes.append("Procede de Fase 4 offline. No requiere prospeccion climatica de campo.")
    for n in climate_data.get("notes", []):
        if n not in notes:
            notes.append(n)

    # Gaps si faltan datos
    gaps: list[InventoryGap] = []
    if not has_classification:
        gaps.append(InventoryGap(
            gap_id="GAP-FI-001-001",
            factor_id="FI-001",
            field="clasificacion_climatica",
            description=(
                "No se dispone de clasificacion climatica completa (Koppen/Martonne). "
                "Requiere datos climaticos mensuales de la estacion mas proxima."
            ),
            criticality="MEDIA",
            resolution_mode="GABINETE",
            status="PENDIENTE",
        ))

    # Semaforo automatico
    semaphore = classify_semaphore_from_evidence(evidence_status, gaps)

    # Justificaciones
    if field_mode == "GABINETE_SUFICIENTE":
        field_mode_just = (
            "Las normales climatologicas AEMET son suficientes para la caracterizacion "
            "del factor Clima en modo gabinete (EIA simplificada). "
            "No se requiere prospeccion meteorologica de campo."
        )
    else:
        field_mode_just = ""

    if has_classification:
        sem_just = (
            f"Clasificacion basada en datos AEMET confirmados de gabinete. "
            f"Koppen: {cc.get('koppen_code', '?')} ({cc.get('koppen_label', '?')})."
        )
    else:
        sem_just = ""

    return FactorInventory(
        factor_id="FI-001",
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
# build_base_factor
# ---------------------------------------------------------------------------

def build_base_factor(
    factor_id: str,
    reason: Optional[str] = None,
) -> FactorInventory:
    """Crea un FactorInventory base con PENDIENTE/NO_CONSTA para factores sin datos especificos.

    Incluye un gap de inventario indicando que faltan fuentes para ese factor.

    Args:
        factor_id: Identificador del factor (FI-001...FI-016).
        reason:    Descripcion del gap (opcional; si None se genera automaticamente).

    Returns:
        FactorInventory con evidence_status=PENDIENTE, field_mode=NO_CONSTA,
        inventory_semaphore=NO_CONSTA, ready_for_impact_assessment=False.
    """
    factor_name = FACTOR_NAMES.get(factor_id, factor_id)
    gap_description = reason or (
        f"Pendiente de incorporar fuentes especificas para {factor_id} ({factor_name}). "
        "No se dispone de integracion automatica para este factor en Fase 4 offline."
    )

    gap = InventoryGap(
        gap_id=f"GAP-{factor_id}-001",
        factor_id=factor_id,
        field="datos_generales",
        description=gap_description,
        criticality="MEDIA",
        resolution_mode="GABINETE",
        status="PENDIENTE",
    )

    note = (
        f"Factor {factor_id} ({factor_name}) inicializado con estado base. "
        "Requiere incorporacion de fuentes especificas en Fase 5. "
        "No se han integrado datos automaticos para este factor en Fase 4 offline."
    )

    return FactorInventory(
        factor_id=factor_id,
        evidence_status="PENDIENTE",
        field_mode="NO_CONSTA",
        inventory_semaphore="NO_CONSTA",
        ready_for_impact_assessment=False,
        description="",
        gaps=[gap],
        notes=[note],
    )


# ---------------------------------------------------------------------------
# build_inventory_from_phase4_data
# ---------------------------------------------------------------------------

def build_inventory_from_phase4_data(
    expediente_id: str,
    phase4_result: dict,
    climate_result: Optional[dict] = None,
    cartography_plan: Optional[dict] = None,
    phase2_data: Optional[dict] = None,
) -> InventorySummary:
    """Construye InventorySummary con 16 factores a partir de los datos de Fase 4.

    FI-001 Clima se construye con datos del pipeline CL-06 si estan disponibles.
    FI-005 e FI-016 se enriquecen mediante IV-03 (factores de riesgo).
    FI-011 e FI-013 se enriquecen mediante IV-04 (factores de contexto).
    Los demás factores se inicializan como base PENDIENTE/NO_CONSTA.

    Args:
        expediente_id:    Identificador del expediente.
        phase4_result:    Dict de Phase4OfflineResult.to_dict() (obligatorio).
        climate_result:   Dict de Phase4ClimateResult.to_dict() (opcional;
                          si None se usa phase4_result["climate"] si existe).
        cartography_plan: Dict del plan cartografico (informativo).
        phase2_data:      Dict de Phase2Result.to_dict() (opcional;
                          si existe, enriquece FI-013 con datos del promotor).

    Returns:
        InventorySummary con 16 factores y all_ready_for_phase6 False
        (salvo caso teorico en que todos esten ready, que en esta version no ocurre).
    """
    extra_warnings: list[str] = []

    # Resolver la fuente de datos climaticos
    effective_climate = climate_result
    if effective_climate is None:
        effective_climate = phase4_result.get("climate")

    if effective_climate is None:
        extra_warnings.append(
            "No se dispone de datos climaticos de Fase 4. "
            "FI-001 Clima queda en estado PENDIENTE/NO_CONSTA."
        )

    if cartography_plan is None and not phase4_result.get("cartography_plan"):
        extra_warnings.append(
            "No se dispone de plan cartografico de Fase 4. "
            "Las fichas de inventario no incluiran referencias cartograficas."
        )

    # Construir los 16 factores en orden canonico
    factors: list[FactorInventory] = []
    for fid in sorted(FACTOR_NAMES.keys()):
        if fid == "FI-001" and effective_climate is not None:
            factors.append(build_climate_factor_from_phase4(effective_climate))
        else:
            factors.append(build_base_factor(fid))

    summary = build_inventory_summary(expediente_id, factors)
    summary.warnings.extend(extra_warnings)

    # Enriquecer FI-005 e FI-016 con IV-03 (factores de riesgo)
    effective_cart = cartography_plan if cartography_plan is not None else phase4_result.get("cartography_plan")
    risk_result = build_risk_inventory_factors_from_phase4(phase4_result, effective_cart)
    summary = merge_risk_factors_into_summary(summary, risk_result.factors)
    summary.warnings.extend(risk_result.warnings)
    summary.notes.extend(risk_result.notes)

    # Enriquecer FI-011 e FI-013 con IV-04 (factores de contexto)
    context_result = build_context_inventory_factors_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_cart,
    )
    summary = merge_context_factors_into_summary(summary, context_result.factors)
    summary.warnings.extend(context_result.warnings)
    summary.notes.extend(context_result.notes)

    # Enriquecer FI-006 e FI-014 con IV-05 (factores de presion)
    pressure_result = build_pressure_inventory_factors_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
    )
    summary = merge_pressure_factors_into_summary(summary, pressure_result.factors)
    summary.warnings.extend(pressure_result.warnings)
    summary.notes.extend(pressure_result.notes)

    # Enriquecer FI-009 e FI-010 con IV-06 (ENP y Red Natura 2000)
    protected_result = build_protected_areas_inventory_factors_from_phase4(
        phase4_result=phase4_result,
        cartography_plan=effective_cart,
    )
    summary = merge_protected_area_factors_into_summary(summary, protected_result.factors)
    summary.warnings.extend(protected_result.warnings)
    summary.notes.extend(protected_result.notes)

    # Enriquecer FI-002, FI-003 e FI-004 con IV-07 (factores fisicos)
    physical_result = build_physical_inventory_factors_from_phase4(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_cart,
    )
    summary = merge_physical_factors_into_summary(summary, physical_result.factors)
    summary.warnings.extend(physical_result.warnings)
    summary.notes.extend(physical_result.notes)

    # Enriquecer FI-015 con IV-08 (Cambio climatico)
    cc_result = build_climate_change_inventory_factor_from_phase4(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        climate_result=effective_climate,
    )
    summary = merge_climate_change_factor_into_summary(summary, cc_result.factor)
    summary.warnings.extend(cc_result.warnings)
    summary.notes.extend(cc_result.notes)

    # Enriquecer FI-012 con IV-09 (Patrimonio cultural)
    heritage_result = build_heritage_inventory_factor_from_phase4(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_cart,
    )
    summary = merge_heritage_factor_into_summary(summary, heritage_result.factor)
    summary.warnings.extend(heritage_result.warnings)
    summary.notes.extend(heritage_result.notes)

    # Enriquecer FI-007 y FI-008 con IV-10 (Flora y Fauna)
    bio_result = build_biodiversity_inventory_factors_from_phase_data(
        phase2_data=phase2_data,
        phase4_result=phase4_result,
        cartography_plan=effective_cart,
    )
    summary = merge_biodiversity_factors_into_summary(summary, bio_result.factors)
    summary.warnings.extend(bio_result.warnings)
    summary.notes.extend(bio_result.notes)

    return summary


# ---------------------------------------------------------------------------
# build_inventory_from_phase4  (función principal)
# ---------------------------------------------------------------------------

def build_inventory_from_phase4(
    expediente_path: "str | Path",
    phase4_result_path: "str | Path | None" = None,
    phase4_climate_result_path: "str | Path | None" = None,
    cartography_plan_path: "str | Path | None" = None,
    write_outputs: bool = False,
    output_dir: str = "inventario",
) -> InventoryBuildResult:
    """Construye el inventario ambiental inicial (Fase 5) desde los outputs de Fase 4.

    Busca por defecto:
    - fase4/phase4_result.json         (obligatorio; FileNotFoundError si no existe)
    - clima/phase4_climate_result.json  (opcional; fallback al "climate" embebido)
    - cartografia/cartografia_plan.json (opcional; informativo)

    Si write_outputs=False (default): solo lectura, no crea archivos.
    Si write_outputs=True: escribe en output_dir/ (por defecto 'inventario/').

    Args:
        expediente_path:           Directorio raiz del expediente.
        phase4_result_path:        Ruta al phase4_result.json (por defecto: fase4/).
        phase4_climate_result_path: Ruta al phase4_climate_result.json (por defecto: clima/).
        cartography_plan_path:     Ruta al cartografia_plan.json (por defecto: cartografia/).
        write_outputs:             Si True, escribe fichas markdown e index JSON.
        output_dir:                Subdirectorio de salida (relativo a expediente_path).

    Returns:
        InventoryBuildResult con el InventorySummary y metadatos del proceso.

    Raises:
        FileNotFoundError: si phase4_result.json no existe.
        ValueError: si phase4_result.json no es JSON valido.
    """
    exp_path = Path(expediente_path).resolve()

    # phase4_result.json — obligatorio salvo compatibilidad legacy AG-08
    p4_path = (
        Path(phase4_result_path)
        if phase4_result_path is not None
        else exp_path / "fase4" / "phase4_result.json"
    )
    try:
        phase4_result = load_json_file(p4_path)
    except FileNotFoundError:
        legacy_index = exp_path / "fichas_inventario" / "indice_inventario.json"
        if not legacy_index.exists():
            raise
        from eia_agent.core.inventory_legacy_adapter import adapt_legacy_inventory_index
        legacy_result = adapt_legacy_inventory_index(
            exp_path,
            legacy_index_path=legacy_index,
            write_outputs=write_outputs,
        )
        notes = list(legacy_result.notes)
        notes.append(
            "Compatibilidad legacy activada: phase4_result.json no existe; "
            "inventario reconstruido desde fichas_inventario/indice_inventario.json."
        )
        rendered_files = [legacy_result.output_path] if legacy_result.output_path else []
        return InventoryBuildResult(
            expediente_id=legacy_result.expediente_id,
            inventory_summary=legacy_result.inventory_summary,
            factor_count=legacy_result.inventory_summary.total_factors,
            ready_count=legacy_result.inventory_summary.ready_count,
            rendered_files=[p for p in rendered_files if p],
            warnings=list(legacy_result.warnings),
            notes=notes,
        )
    expediente_id = phase4_result.get("expediente_id", exp_path.name)

    warnings: list[str] = []
    notes: list[str] = []

    # climate_result — opcional
    climate_result: Optional[dict] = None
    if phase4_climate_result_path is not None:
        try:
            climate_result = load_json_file(phase4_climate_result_path)
        except FileNotFoundError:
            warnings.append(
                f"Archivo phase4_climate_result no encontrado: "
                f"{phase4_climate_result_path}. "
                "Usando datos embebidos en phase4_result si existen."
            )
        except ValueError as exc:
            warnings.append(f"Error al leer phase4_climate_result: {exc}")
    else:
        default_climate = exp_path / "clima" / "phase4_climate_result.json"
        if default_climate.exists():
            try:
                climate_result = load_json_file(default_climate)
            except ValueError as exc:
                warnings.append(f"Error al leer clima/phase4_climate_result.json: {exc}")

    # cartography_plan — opcional
    cartography_plan: Optional[dict] = None
    if cartography_plan_path is not None:
        try:
            cartography_plan = load_json_file(cartography_plan_path)
        except FileNotFoundError:
            warnings.append(
                f"Archivo cartografia_plan no encontrado: {cartography_plan_path}."
            )
        except ValueError as exc:
            warnings.append(f"Error al leer cartografia_plan: {exc}")
    else:
        default_cart = exp_path / "cartografia" / "cartografia_plan.json"
        if default_cart.exists():
            try:
                cartography_plan = load_json_file(default_cart)
            except ValueError as exc:
                warnings.append(f"Error al leer cartografia/cartografia_plan.json: {exc}")

    # phase2_data — opcional; enriquece FI-013
    phase2_data: Optional[dict] = None
    default_phase2 = exp_path / "control_interno" / "phase2_result.json"
    if default_phase2.exists():
        try:
            phase2_data = load_json_file(default_phase2)
        except ValueError as exc:
            warnings.append(f"Error al leer control_interno/phase2_result.json: {exc}")

    # Construir InventorySummary
    inventory_summary = build_inventory_from_phase4_data(
        expediente_id=expediente_id,
        phase4_result=phase4_result,
        climate_result=climate_result,
        cartography_plan=cartography_plan,
        phase2_data=phase2_data,
    )

    # Escribir outputs si se solicita
    rendered_files: list[str] = []
    if write_outputs:
        out_dir = exp_path / output_dir
        render_result = write_inventory_markdown_files(inventory_summary, out_dir)
        rendered_files.extend(render_result.factor_files)
        if render_result.summary_file:
            rendered_files.append(render_result.summary_file)
        if render_result.index_file:
            rendered_files.append(render_result.index_file)

        # inventory_summary.json
        summary_json_path = out_dir / "inventory_summary.json"
        summary_json_path.write_text(
            json.dumps(inventory_summary.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rendered_files.append(str(summary_json_path))
        notes.append(f"Outputs escritos en: {out_dir}")

    # Nota de informacion
    has_climate = climate_result is not None or phase4_result.get("climate") is not None
    notes.append(
        f"Inventario Fase 5 inicial construido desde Fase 4 offline. "
        f"FI-001 Clima: {'con datos CL-06' if has_climate else 'sin datos (PENDIENTE)'}. "
        f"FI-011/FI-013: {'con datos Fase 2' if phase2_data else 'sin datos Fase 2'}. "
        "Factores base restantes: estado PENDIENTE/NO_CONSTA."
    )

    return InventoryBuildResult(
        expediente_id=expediente_id,
        inventory_summary=inventory_summary,
        factor_count=inventory_summary.total_factors,
        ready_count=inventory_summary.ready_count,
        rendered_files=rendered_files,
        warnings=warnings,
        notes=notes,
    )
