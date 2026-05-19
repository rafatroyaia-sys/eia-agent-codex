"""
cartography_plan -- CA-10
Planificador cartográfico offline para Fase 4.

Lee phase2_result.json, extrae GeoPoint (CA-09), construye los extents
estándar y genera especificaciones de los 6 mapas mínimos obligatorios.
No genera imágenes. No llama a APIs externas.

Uso:
    from eia_agent.core.cartography_plan import build_cartography_plan

    result = build_cartography_plan("expediente-EIA-2026-RECIMETAL-NAVE-222")
    print(result.summary())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from eia_agent.core.geospatial_utils import (
    GeoPoint,
    build_standard_map_extents,
    extract_geopoint_from_phase2,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_UNRELIABLE_STATUSES = frozenset({"ESTIMADO", "PROVISIONAL", "NO_DECLARADO"})

_MAP_DEFINITIONS: list[dict] = [
    {
        "map_id": "MAP-001",
        "title": "Situación general",
        "purpose": "Localización del proyecto en su contexto territorial regional",
        "map_type": "situacion_general",
        "extent_key": "situacion_general",
        "required_layers": ["base_territorial", "marcador_proyecto"],
        "source_candidates": [
            "IGN / BTN100",
            "PNOA / ortofoto baja resolución",
            "Cartografía base autonómica",
        ],
        "output_filename": "MAP-001_situacion_general.png",
    },
    {
        "map_id": "MAP-002",
        "title": "Emplazamiento",
        "purpose": "Localización precisa del emplazamiento en su entorno inmediato",
        "map_type": "emplazamiento",
        "extent_key": "emplazamiento",
        "required_layers": ["ortofoto", "marcador_proyecto", "viario"],
        "source_candidates": [
            "PNOA / ortofoto alta resolución",
            "IGN / Serie BTN25",
            "Grafcan / OrtoExpress Canarias",
        ],
        "output_filename": "MAP-002_emplazamiento.png",
    },
    {
        "map_id": "MAP-003",
        "title": "Parcela / catastro",
        "purpose": "Delimitación catastral de la parcela y su entorno inmediato",
        "map_type": "parcela_catastro",
        "extent_key": "detalle_parcela",
        "required_layers": ["catastro", "parcela", "marcador_proyecto"],
        "source_candidates": [
            "Catastro / Sede electrónica WMS",
            "Grafcan / Catastro Canarias",
            "SIGPAC",
        ],
        "output_filename": "MAP-003_parcela_catastro.png",
    },
    {
        "map_id": "MAP-004",
        "title": "Red Natura 2000 / ENP",
        "purpose": "Distancia y relación con espacios protegidos Red Natura 2000 y ENP",
        "map_type": "red_natura_enp",
        "extent_key": "situacion_general",
        "required_layers": [
            "red_natura_2000",
            "espacios_naturales_protegidos",
            "marcador_proyecto",
        ],
        "source_candidates": [
            "MITERD / Red Natura 2000 INSPIRE",
            "Grafcan / ENP Canarias",
            "IECA / ENP Andalucía",
        ],
        "output_filename": "MAP-004_red_natura_enp.png",
    },
    {
        "map_id": "MAP-005",
        "title": "Usos del suelo entorno",
        "purpose": "Usos del suelo y presencia de receptores sensibles en radio 500 m",
        "map_type": "usos_suelo",
        "extent_key": "entorno_500m",
        "required_layers": ["usos_suelo", "buffer_500m", "marcador_proyecto"],
        "source_candidates": [
            "Corine Land Cover / IGN",
            "SIOSE / IGN",
            "Grafcan / Mapa usos del suelo Canarias",
        ],
        "output_filename": "MAP-005_usos_suelo_entorno.png",
    },
    {
        "map_id": "MAP-006",
        "title": "Inundabilidad / riesgos físicos",
        "purpose": "Zonas de inundabilidad y riesgos físicos en radio 2 000 m",
        "map_type": "inundabilidad_riesgos",
        "extent_key": "entorno_2000m",
        "required_layers": ["inundabilidad", "drenaje", "marcador_proyecto"],
        "source_candidates": [
            "MITERD / SNCZI Sistema Nacional Cartografía Zonas Inundables",
            "IGME / Mapa de riesgos geológicos",
            "Grafcan / RIESGOMAP Canarias",
        ],
        "output_filename": "MAP-006_inundabilidad_riesgos.png",
    },
]


# ---------------------------------------------------------------------------
# MapSpec
# ---------------------------------------------------------------------------

@dataclass
class MapSpec:
    """Especificación de un mapa cartográfico para la Fase 4 EIA."""

    map_id: str
    title: str
    purpose: str
    map_type: str
    extent_key: str
    extent: dict
    required_layers: list[str]
    source_candidates: list[str]
    output_filename: str
    status: str
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "map_id": self.map_id,
            "title": self.title,
            "purpose": self.purpose,
            "map_type": self.map_type,
            "extent_key": self.extent_key,
            "extent": self.extent,
            "required_layers": list(self.required_layers),
            "source_candidates": list(self.source_candidates),
            "output_filename": self.output_filename,
            "status": self.status,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"{self.map_id} — {self.title} [{self.status}]",
            f"  Tipo    : {self.map_type}",
            f"  Extent  : {self.extent_key}",
            f"  Salida  : {self.output_filename}",
            f"  Capas   : {', '.join(self.required_layers)}",
        ]
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CartographyPlanResult
# ---------------------------------------------------------------------------

@dataclass
class CartographyPlanResult:
    """Resultado del planificador cartográfico offline (CA-10)."""

    expediente_id: str
    center: dict
    maps: list[MapSpec]
    ready_for_render: bool
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "center": self.center,
            "maps": [m.to_dict() for m in self.maps],
            "ready_for_render": self.ready_for_render,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        ready_label = "LISTO PARA RENDERIZAR" if self.ready_for_render else "PLANIFICADO (pendiente de validación)"
        lines = [
            f"Plan cartográfico — {self.expediente_id}",
            f"  Estado  : {ready_label}",
            f"  Centro  : ({self.center.get('lat', '?'):.5f}, {self.center.get('lon', '?'):.5f})"
            f" [{self.center.get('status', '?')}]",
            f"  Mapas   : {len(self.maps)}",
        ]
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        lines.append("")
        for m in self.maps:
            lines.append(f"  {m.map_id} [{m.status}] — {m.title}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generador de especificaciones de mapas
# ---------------------------------------------------------------------------

def _build_map_specs(point: GeoPoint, extents: dict) -> list[MapSpec]:
    """Construye las especificaciones de los 6 mapas mínimos."""
    unreliable = point.status in _UNRELIABLE_STATUSES
    status = "PLANNED" if unreliable else "READY_FOR_RENDER"

    specs: list[MapSpec] = []
    for defn in _MAP_DEFINITIONS:
        ext_key = defn["extent_key"]
        extent_obj = extents.get(ext_key)
        extent_dict = extent_obj.to_dict() if extent_obj is not None else {}

        warnings: list[str] = []
        if unreliable:
            warnings.append(
                f"Coordenadas con estado '{point.status}'. "
                "El extent debe revisarse cuando el punto sea VERIFICADO o DECLARADO."
            )

        specs.append(MapSpec(
            map_id=defn["map_id"],
            title=defn["title"],
            purpose=defn["purpose"],
            map_type=defn["map_type"],
            extent_key=ext_key,
            extent=extent_dict,
            required_layers=list(defn["required_layers"]),
            source_candidates=list(defn["source_candidates"]),
            output_filename=defn["output_filename"],
            status=status,
            warnings=warnings,
            notes=[],
        ))

    return specs


# ---------------------------------------------------------------------------
# build_cartography_plan_markdown
# ---------------------------------------------------------------------------

def build_cartography_plan_markdown(result: CartographyPlanResult) -> str:
    """Genera el markdown del plan cartográfico."""
    center = result.center
    lat = center.get("lat", "?")
    lon = center.get("lon", "?")
    coord_status = center.get("status", "?")
    ready_label = "LISTO PARA RENDERIZAR" if result.ready_for_render else "PLANIFICADO — pendiente de validación de coordenadas"

    lines: list[str] = [
        f"# Plan cartográfico — {result.expediente_id}",
        "",
        "> **AVISO**: Este plan no contiene cartografía generada; solo especificaciones "
        "para renderizado posterior mediante módulos CA-11 o superiores.",
        "",
        "## Datos del emplazamiento",
        "",
        f"- **Coordenadas centro**: {lat:.5f}, {lon:.5f} (WGS84)",
        f"- **Estado coordenadas**: {coord_status}",
        f"- **Estado del plan**: {ready_label}",
        f"- **Mapas planificados**: {len(result.maps)}",
        "",
    ]

    if result.warnings:
        lines.append("## Avisos")
        lines.append("")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        "## Mapas planificados",
        "",
        "| ID | Título | Tipo | Extent | Estado | Salida |",
        "|----|--------|------|--------|--------|--------|",
    ]
    for m in result.maps:
        lines.append(
            f"| {m.map_id} | {m.title} | {m.map_type} | {m.extent_key} | {m.status} | `{m.output_filename}` |"
        )

    lines.append("")
    lines.append("## Detalle por mapa")
    lines.append("")

    for m in result.maps:
        lines += [
            f"### {m.map_id} — {m.title}",
            "",
            f"**Propósito**: {m.purpose}  ",
            f"**Estado**: {m.status}  ",
            f"**Extent**: {m.extent_key}  ",
            f"**Salida esperada**: `{m.output_filename}`",
            "",
            "**Capas requeridas**:",
            "",
        ]
        for layer in m.required_layers:
            lines.append(f"- `{layer}`")
        lines.append("")
        lines.append("**Fuentes candidatas**:")
        lines.append("")
        for src in m.source_candidates:
            lines.append(f"- {src}")
        lines.append("")
        if m.warnings:
            for w in m.warnings:
                lines.append(f"> ⚠️ {w}")
            lines.append("")

    if result.notes:
        lines.append("## Notas")
        lines.append("")
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")

    lines += [
        "---",
        "",
        "*Generado por CA-10 — Planificador cartográfico offline.*  ",
        "*No contiene datos geoespaciales descargados ni imágenes generadas.*",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_cartography_plan
# ---------------------------------------------------------------------------

def build_cartography_plan(
    expediente_path: str | Path,
    phase2_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "cartografia",
) -> CartographyPlanResult:
    """Genera el plan cartográfico offline para la Fase 4.

    Args:
        expediente_path:    Ruta al directorio del expediente.
        phase2_result_path: Ruta al phase2_result.json. Por defecto:
                            <expediente>/control_interno/phase2_result.json
        write_outputs:      Si True, escribe JSON y MD en <expediente>/<output_dir>/.
        output_dir:         Subdirectorio de salida (por defecto "cartografia").

    Returns:
        CartographyPlanResult con los 6 MapSpec y metadatos del plan.

    Raises:
        FileNotFoundError: Si phase2_result.json no existe.
        ValueError: Si no se pueden extraer coordenadas WGS84.
    """
    exp_path = Path(expediente_path)
    expediente_id = exp_path.name

    if phase2_result_path is None:
        p2_path = exp_path / "control_interno" / "phase2_result.json"
    else:
        p2_path = Path(phase2_result_path)

    if not p2_path.exists():
        raise FileNotFoundError(
            f"No se encontró phase2_result.json en: {p2_path}. "
            "Ejecute Fase 2 antes de planificar la cartografía."
        )

    with open(p2_path, encoding="utf-8") as fh:
        phase2_data = json.load(fh)

    point: GeoPoint = extract_geopoint_from_phase2(phase2_data)
    extents = build_standard_map_extents(point)

    map_specs = _build_map_specs(point, extents)

    warnings: list[str] = []
    notes: list[str] = []

    if point.status in _UNRELIABLE_STATUSES:
        warnings.append(
            f"Las coordenadas del emplazamiento tienen estado '{point.status}'. "
            "Confirmar antes de iniciar el renderizado cartográfico."
        )

    ready_for_render = (
        all(m.status == "READY_FOR_RENDER" for m in map_specs)
        and len(warnings) == 0
    )

    notes.append(
        "Plan generado en modo offline. "
        "No se han descargado capas ni se han generado imágenes. "
        "Use módulos CA-11 o superiores para el renderizado."
    )

    result = CartographyPlanResult(
        expediente_id=expediente_id,
        center=point.to_dict(),
        maps=map_specs,
        ready_for_render=ready_for_render,
        warnings=warnings,
        notes=notes,
    )

    if write_outputs:
        out_path = exp_path / output_dir
        out_path.mkdir(parents=True, exist_ok=True)

        json_path = out_path / "cartografia_plan.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

        md_path = out_path / "cartografia_plan.md"
        md_content = build_cartography_plan_markdown(result)
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(md_content)

        result.notes.append(
            f"Outputs escritos en: {out_path} "
            "(cartografia_plan.json, cartografia_plan.md)"
        )

    return result
