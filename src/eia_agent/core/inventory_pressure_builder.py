"""
inventory_pressure_builder -- IV-05
Constructor de factores FI-006 Calidad del aire y FI-014 Ruido
desde Fase 2/Fase 4 offline.

Lee los outputs de Fase 2 (phase2_result.json / object_scope) y Fase 4
(phase4_result.json) para detectar, mediante texto, operaciones con
potencial de emision de polvo/gases o generacion de ruido, y construye
los factores FI-006 e FI-014 con estado ESTIMADO/PENDIENTE y semaforo
AMARILLO/ROJO_AMARILLO/NO_CONSTA segun la informacion disponible.

Reglas de prudencia aplicadas:
  - FI-006: no se afirma "sin emisiones", "no hay polvo" ni "sin afeccion
    a la calidad del aire". Nunca VERDE.
  - FI-014: no se afirma "sin ruido", "cumple limites", "sin afeccion
    acustica" ni "impacto compatible". Nunca VERDE.
  - Ninguna descripcion contiene "moderado", "severo", "critico"
    (valoracion de impacto = Fase 6).
  - ready_for_impact_assessment = False siempre para ambos factores.
  - inventory_semaphore nunca VERDE para ninguno de los dos factores.

No consulta WMS ni WMTS.
No verifica emisiones reales ni niveles acusticos medidos.
No consulta normativa de emisiones ni ruido.
No valora impactos.
No genera Fase 6.
No usa IA.
No llama a APIs externas.

Depende de:
  IV-00 (inventory_model) — FactorInventory, InventoryGap, InventorySummary
  OB-06 (phase2_pipeline) — estructura phase2_result.json
  F4-01 (phase4_offline_pipeline) — estructura phase4_result.json
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

_AIR_QUALITY_TERMS: list[str] = [
    "tritura",
    "criba",
    "cribado",
    "machaca",
    "molino",
    "molienda",
    "corte",
    "cortar",
    "serrar",
    "aserrado",
    "demolic",
    "voladura",
    "excavac",
    "movimiento de tierra",
    "movimientos de tierra",
    "carga de material",
    "descarga de material",
    "acopio",
    "polvo",
    "particulas",
    "emision",
    "gases",
    "combustion",
    "diesel",
    "gasoil",
    "generador",
    "soldadura",
    "pintura",
    "disolvente",
    "volatil",
    "cov",
    "nox",
    "sox",
    "incineracion",
    "quema",
]

_AIR_QUALITY_HIGH_TERMS: list[str] = [
    "tritura",
    "cribado",
    "criba",
    "machaca",
    "molino",
    "molienda",
    "corte",
    "cortar",
    "serrar",
    "aserrado",
    "demolic",
    "voladura",
]

_AIR_QUALITY_FILTRATION_TERMS: list[str] = [
    "filtro",
    "filtracion",
    "aspiracion",
    "extraccion",
    "captacion de polvo",
    "depurador",
    "scrubber",
    "ciclone",
    "manga",
    "electrostatico",
    "biofiltro",
]

_NOISE_TERMS: list[str] = [
    "tritura",
    "cribado",
    "criba",
    "machaca",
    "molino",
    "molienda",
    "cizalla",
    "prensa",
    "compresor",
    "generador",
    "diesel",
    "gasoil",
    "maquinaria pesada",
    "maquinaria movil",
    "carga",
    "descarga",
    "manipulacion",
    "cortadora",
    "sierra",
    "torno",
    "fresa",
    "taladro",
    "martillo",
    "percusion",
    "impacto",
    "vibracion",
    "ventilador",
    "motor",
    "camion",
    "vehiculo",
    "trafico",
    "transporte",
    "demolic",
    "voladura",
    "excavac",
]

_NOISE_HIGH_TERMS: list[str] = [
    "tritura",
    "molino",
    "molienda",
    "cizalla",
    "prensa",
    "compresor",
    "generador",
    "diesel",
    "gasoil",
    "maquinaria pesada",
    "percusion",
    "impacto",
    "martillo",
    "demolic",
    "voladura",
]

# ---------------------------------------------------------------------------
# Extraccion de texto de actividad
# ---------------------------------------------------------------------------


def extract_activity_text(
    phase2_data: dict | None,
    phase4_result: dict | None,
) -> str:
    """Extrae texto de actividad de phase2_data y phase4_result para deteccion de terminos.

    Prioriza object_scope.operaciones_incluidas de Fase 2.
    Fallback: cualquier texto en phase4_result.object_scope si existe.
    Devuelve str en minusculas.
    """
    parts: list[str] = []

    if phase2_data:
        scope = phase2_data.get("object_scope") or {}
        ops = scope.get("operaciones_incluidas") or []
        if isinstance(ops, list):
            parts.extend(str(op) for op in ops if op)
        elif isinstance(ops, str) and ops:
            parts.append(ops)
        # Tambien descripcion de actividad si existe
        descripcion = scope.get("descripcion_actividad") or scope.get("actividad") or ""
        if descripcion:
            parts.append(str(descripcion))
        # Nombre del proyecto puede aportar contexto
        nombre = scope.get("denominacion") or scope.get("nombre_proyecto") or ""
        if nombre:
            parts.append(str(nombre))

    # Fallback desde phase4_result
    if phase4_result:
        p4_scope = phase4_result.get("object_scope") or {}
        if p4_scope:
            ops4 = p4_scope.get("operaciones_incluidas") or []
            if isinstance(ops4, list):
                parts.extend(str(op) for op in ops4 if op)
            elif isinstance(ops4, str) and ops4:
                parts.append(ops4)

    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Deteccion de operaciones relevantes
# ---------------------------------------------------------------------------


def detect_air_quality_relevant_operations(text: str) -> list[str]:
    """Detecta terminos de emision de polvo/gases en texto de actividad.

    Devuelve lista de terminos encontrados (sin duplicados, en orden de aparicion).
    """
    found: list[str] = []
    for term in _AIR_QUALITY_TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def detect_noise_relevant_operations(text: str) -> list[str]:
    """Detecta terminos de generacion de ruido en texto de actividad.

    Devuelve lista de terminos encontrados (sin duplicados, en orden de aparicion).
    """
    found: list[str] = []
    for term in _NOISE_TERMS:
        if term in text and term not in found:
            found.append(term)
    return found


def _has_high_air_quality_terms(found_terms: list[str]) -> bool:
    return any(t in _AIR_QUALITY_HIGH_TERMS for t in found_terms)


def _has_filtration_terms(text: str) -> bool:
    return any(t in text for t in _AIR_QUALITY_FILTRATION_TERMS)


def _has_high_noise_terms(found_terms: list[str]) -> bool:
    return any(t in _NOISE_HIGH_TERMS for t in found_terms)


# ---------------------------------------------------------------------------
# Dataclass resultado
# ---------------------------------------------------------------------------


@dataclass
class PressureInventoryBuildResult:
    """Resultado de IV-05: FI-006 Calidad del aire + FI-014 Ruido."""

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
        lines = ["PressureInventoryBuildResult:"]
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
# Constructor FI-006 Calidad del aire
# ---------------------------------------------------------------------------


def build_air_quality_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
) -> FactorInventory:
    """Construye FI-006 Calidad del aire desde datos de Fase 2 y Fase 4.

    Logica:
      - Sin texto de actividad: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Terminos presentes, sin alta presion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO
      - Terminos de alta presion sin filtracion: ESTIMADO / CAMPO_RECOMENDADO / ROJO_AMARILLO
      - Terminos de alta presion con filtracion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    Gaps:
      GAP-FI-006-001: medicion de calidad del aire — siempre, ALTA, CAMPO
      GAP-FI-006-002: sistema de control de emisiones — solo si alta presion sin filtracion, ALTA, GABINETE
    """
    fid = "FI-006"
    fname = FACTOR_NAMES.get(fid, "Calidad del aire")

    activity_text = extract_activity_text(phase2_data, phase4_result)
    found_terms = detect_air_quality_relevant_operations(activity_text)

    gaps: list[InventoryGap] = []
    data_sources: list[str] = []

    if found_terms:
        data_sources.append("Operaciones incluidas declaradas en Fase 2")
        high = _has_high_air_quality_terms(found_terms)
        filtration = _has_filtration_terms(activity_text)

        if high and not filtration:
            evidence_status = "ESTIMADO"
            field_mode = "CAMPO_RECOMENDADO"
            inventory_semaphore = "ROJO_AMARILLO"
            description = (
                f"Se detectan operaciones con potencial de generacion de polvo y/o "
                f"particulas en suspension a partir de las operaciones declaradas "
                f"({', '.join(found_terms[:5])}). "
                "No consta sistema de captacion o filtracion de emisiones en la documentacion aportada. "
                "Requiere caracterizacion de campo y revision de medidas preventivas."
            )
        else:
            evidence_status = "ESTIMADO"
            field_mode = "CAMPO_RECOMENDADO"
            inventory_semaphore = "AMARILLO"
            if high:
                description = (
                    f"Se detectan operaciones con potencial de emision de polvo/particulas "
                    f"({', '.join(found_terms[:5])}). "
                    "Constan referencias a sistemas de control en la documentacion. "
                    "Requiere verificacion de campo y caracterizacion de los focos emisores."
                )
            else:
                description = (
                    f"Se detectan operaciones con posible generacion de polvo, gases o "
                    f"particulas ({', '.join(found_terms[:5])}). "
                    "Requiere caracterizacion de campo de los focos de emision."
                )

        # Gap siempre
        gaps.append(
            InventoryGap(
                gap_id="GAP-FI-006-001",
                factor_id="FI-006",
                field="medicion_calidad_aire",
                description=(
                    "Ausencia de medicion o caracterizacion de la calidad del aire en el entorno "
                    "del emplazamiento. Requiere muestreo o revision de datos de estaciones "
                    "de referencia proximas."
                ),
                criticality="ALTA",
                resolution_mode="CAMPO",
                status="PENDIENTE",
            )
        )

        # Gap adicional si alta presion sin filtracion
        if high and not filtration:
            gaps.append(
                InventoryGap(
                    gap_id="GAP-FI-006-002",
                    factor_id="FI-006",
                    field="sistema_control_emisiones",
                    description=(
                        "No consta en la documentacion aportada descripcion de sistemas de "
                        "captacion, filtracion o control de emisiones difusas asociados a las "
                        "operaciones de alta presion detectadas. Requiere aportacion documental."
                    ),
                    criticality="ALTA",
                    resolution_mode="GABINETE",
                    status="PENDIENTE",
                )
            )

    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de descripcion de operaciones que permita evaluar el potencial "
            "de emision de polvo, particulas o gases. Requiere informacion sobre las "
            "actividades previstas."
        )
        gaps.append(
            InventoryGap(
                gap_id="GAP-FI-006-001",
                factor_id="FI-006",
                field="medicion_calidad_aire",
                description=(
                    "Ausencia de descripcion de operaciones y de datos de calidad del aire "
                    "en el entorno. Requiere informacion de actividad y caracterizacion de campo."
                ),
                criticality="ALTA",
                resolution_mode="CAMPO",
                status="PENDIENTE",
            )
        )

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
# Constructor FI-014 Ruido
# ---------------------------------------------------------------------------


def build_noise_factor_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
) -> FactorInventory:
    """Construye FI-014 Ruido desde datos de Fase 2 y Fase 4.

    Logica:
      - Sin texto de actividad: PENDIENTE / NO_CONSTA / NO_CONSTA
      - Terminos de ruido alto: ESTIMADO / CAMPO_NECESARIO / ROJO_AMARILLO
      - Terminos de ruido sin alta presion: ESTIMADO / CAMPO_RECOMENDADO / AMARILLO

    Gaps:
      GAP-FI-014-001: medicion acustica — siempre, ALTA, CAMPO si alta presion; MEDIA, CAMPO si no
      GAP-FI-014-002: horario de operacion y periodos criticos — solo si alta presion, MEDIA, GABINETE
    """
    fid = "FI-014"
    fname = FACTOR_NAMES.get(fid, "Ruido")

    activity_text = extract_activity_text(phase2_data, phase4_result)
    found_terms = detect_noise_relevant_operations(activity_text)

    gaps: list[InventoryGap] = []
    data_sources: list[str] = []

    if found_terms:
        data_sources.append("Operaciones incluidas declaradas en Fase 2")
        high = _has_high_noise_terms(found_terms)

        if high:
            evidence_status = "ESTIMADO"
            field_mode = "CAMPO_NECESARIO"
            inventory_semaphore = "ROJO_AMARILLO"
            description = (
                f"Se detectan operaciones con elevado potencial de generacion de ruido "
                f"({', '.join(found_terms[:5])}). "
                "La presencia de maquinaria de impacto, percusion o de gran potencia acustica "
                "requiere medicion de campo y evaluacion de niveles sonoros en el entorno."
            )
            gaps.append(
                InventoryGap(
                    gap_id="GAP-FI-014-001",
                    factor_id="FI-014",
                    field="medicion_acustica",
                    description=(
                        "Ausencia de medicion acustica de referencia en el emplazamiento y su "
                        "entorno. La presencia de operaciones de alta potencia acustica hace "
                        "necesaria la realizacion de mediciones de campo."
                    ),
                    criticality="ALTA",
                    resolution_mode="CAMPO",
                    status="PENDIENTE",
                )
            )
            gaps.append(
                InventoryGap(
                    gap_id="GAP-FI-014-002",
                    factor_id="FI-014",
                    field="horario_operacion_receptores",
                    description=(
                        "No consta descripcion del horario de operacion, periodos diurno/nocturno "
                        "ni identificacion de receptores sensibles proximos. Requiere aportacion "
                        "documental para completar la caracterizacion acustica."
                    ),
                    criticality="MEDIA",
                    resolution_mode="GABINETE",
                    status="PENDIENTE",
                )
            )
        else:
            evidence_status = "ESTIMADO"
            field_mode = "CAMPO_RECOMENDADO"
            inventory_semaphore = "AMARILLO"
            description = (
                f"Se detectan operaciones con potencial de generacion de ruido "
                f"({', '.join(found_terms[:5])}). "
                "Requiere caracterizacion del entorno acustico y revision de los niveles "
                "de emision previstos."
            )
            gaps.append(
                InventoryGap(
                    gap_id="GAP-FI-014-001",
                    factor_id="FI-014",
                    field="medicion_acustica",
                    description=(
                        "Ausencia de datos acusticos de referencia en el emplazamiento. "
                        "Se recomienda medicion de campo del nivel sonoro equivalente en "
                        "el entorno proximal."
                    ),
                    criticality="MEDIA",
                    resolution_mode="CAMPO",
                    status="PENDIENTE",
                )
            )

    else:
        evidence_status = "PENDIENTE"
        field_mode = "NO_CONSTA"
        inventory_semaphore = "NO_CONSTA"
        description = (
            "No se dispone de descripcion de operaciones que permita evaluar el potencial "
            "de generacion de ruido. Requiere informacion sobre las actividades previstas."
        )
        gaps.append(
            InventoryGap(
                gap_id="GAP-FI-014-001",
                factor_id="FI-014",
                field="medicion_acustica",
                description=(
                    "Ausencia de descripcion de operaciones y de datos acusticos de referencia. "
                    "Requiere informacion de actividad y caracterizacion acustica de campo."
                ),
                criticality="MEDIA",
                resolution_mode="CAMPO",
                status="PENDIENTE",
            )
        )

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


def build_pressure_inventory_factors_from_phase_data(
    phase2_data: dict | None = None,
    phase4_result: dict | None = None,
) -> PressureInventoryBuildResult:
    """Construye FI-006 y FI-014 y los devuelve como PressureInventoryBuildResult."""
    warnings: list[str] = []
    notes: list[str] = []

    fi006 = build_air_quality_factor_from_phase_data(phase2_data, phase4_result)
    fi014 = build_noise_factor_from_phase_data(phase2_data, phase4_result)

    if fi006.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-006 Calidad del aire: sin descripcion de operaciones en Fase 2. "
            "Enriquecer con datos del promotor."
        )
    if fi014.evidence_status == "PENDIENTE":
        warnings.append(
            "FI-014 Ruido: sin descripcion de operaciones en Fase 2. "
            "Enriquecer con datos del promotor."
        )

    notes.append(
        f"IV-05: FI-006={fi006.evidence_status}/{fi006.inventory_semaphore}, "
        f"FI-014={fi014.evidence_status}/{fi014.inventory_semaphore}."
    )

    return PressureInventoryBuildResult(
        factors=[fi006, fi014],
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Merge en InventorySummary
# ---------------------------------------------------------------------------


def merge_pressure_factors_into_summary(
    summary: InventorySummary,
    pressure_factors: list[FactorInventory],
) -> InventorySummary:
    """Sustituye FI-006 y/o FI-014 en un InventorySummary sin mutar el original.

    Preserva el orden canonico de FACTOR_NAMES.
    Propaga warnings y notes del summary original.
    """
    replace_ids = {f.factor_id for f in pressure_factors}
    merged_map = {f.factor_id: f for f in summary.factors}
    for pf in pressure_factors:
        merged_map[pf.factor_id] = pf

    merged_factors = [merged_map[fid] for fid in sorted(FACTOR_NAMES.keys()) if fid in merged_map]

    new_summary = build_inventory_summary(summary.expediente_id, merged_factors)
    new_summary.warnings = list(summary.warnings)
    new_summary.notes = list(summary.notes)
    return new_summary
