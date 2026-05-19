"""
phase4_offline_pipeline -- F4-01
Pipeline integrador de Fase 4 offline (modo test).

Coordina en secuencia:
  CA-08 → run_phase4_precheck
  CL-06 → run_phase4_climate
  CA-10 → build_cartography_plan
  CA-11 → generate_schematic_maps_from_plan

No llama a AEMET, Mapbox ni WMS/WMTS.
No genera cartografía oficial.
No modifica inputs.
No escribe nada salvo write_outputs=True.

Los outputs generados son provisionales y no aptos para presentación administrativa.

Uso:
    from eia_agent.core.phase4_offline_pipeline import run_phase4_offline

    result = run_phase4_offline(
        "expediente-EIA-NAVE-222",
        stations_path="config/estaciones.json",
        climate_data_path="config/datos_climaticos.json",
    )
    print(result.summary())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Phase4OfflineResult
# ---------------------------------------------------------------------------

@dataclass
class Phase4OfflineResult:
    """Resultado del pipeline de Fase 4 offline."""

    expediente_id: str
    precheck: dict
    climate: dict | None
    cartography_plan: dict | None
    schematic_maps: list[dict]
    ready_for_phase5: bool
    administrative_ready: bool   # Siempre False en este pipeline
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "precheck": self.precheck,
            "climate": self.climate,
            "cartography_plan": self.cartography_plan,
            "schematic_maps": list(self.schematic_maps),
            "ready_for_phase5": self.ready_for_phase5,
            "administrative_ready": self.administrative_ready,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Fase 4 offline — {self.expediente_id}",
            f"  Listo para Fase 5  : {'SI' if self.ready_for_phase5 else 'NO'}",
            "  Válido administrat. : NO (modo test offline)",
        ]

        if self.climate:
            station = (self.climate.get("selected_station") or {}).get("name", "?")
            dist = self.climate.get("station_distance_km")
            dist_str = f"{dist:.1f} km" if dist is not None else "?"
            koppen = ((self.climate.get("climate_classification") or {})
                      .get("koppen_code", "?"))
            lines.append(f"  Estación climática : {station} ({dist_str})")
            lines.append(f"  Köppen             : {koppen}")
        else:
            lines.append("  Clima              : NO COMPLETADO")

        n_maps = len(self.schematic_maps)
        lines.append(f"  Mapas              : {n_maps}/6")

        for w in self.warnings:
            lines.append(f"  AVISO: {w}")

        lines.append(
            "  NOTA: Fase 4 offline. No apta para presentación administrativa."
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# build_phase4_offline_markdown
# ---------------------------------------------------------------------------

def build_phase4_offline_markdown(result: Phase4OfflineResult) -> str:
    """Genera el markdown resumen de la Fase 4 offline."""
    lines = [
        f"# Fase 4 offline — {result.expediente_id}",
        "",
        "> **NOTA**: Esta Fase 4 ha sido completada en modo test/offline. "
        "No es apta para presentación administrativa. "
        "La cartografía es esquemática y no contiene datos WMS/WMTS oficiales.",
        "",
        "## Estado general",
        "",
        f"- **Listo para Fase 5**: {'Sí' if result.ready_for_phase5 else 'No'}",
        "- **Válido administrativamente**: No (modo test offline)",
        f"- **Expediente**: {result.expediente_id}",
        "",
    ]

    # --- Precheck ---
    lines.append("## Precheck Fase 4 (CA-08)")
    lines.append("")
    if result.precheck:
        issues = result.precheck.get("issues", [])
        errors = sum(1 for i in issues if i.get("severity") == "ERROR")
        warns = sum(1 for i in issues if i.get("severity") == "WARNING")
        lines += [
            f"- **Errores**: {errors}",
            f"- **Avisos**: {warns}",
        ]
        if errors == 0:
            lines.append("- **Estado**: OK (sin errores bloqueantes)")
        else:
            lines.append("- **Estado**: CON ERRORES — revisar antes de avanzar")
    else:
        lines.append("- Precheck no ejecutado.")
    lines.append("")

    # --- Clima ---
    lines.append("## Clima (CL-06)")
    lines.append("")
    if result.climate:
        station = (result.climate.get("selected_station") or {})
        station_name = station.get("name", "No identificada")
        dist = result.climate.get("station_distance_km")
        sel_status = result.climate.get("station_selection_status", "?")
        lines += [
            f"- **Estación**: {station_name}",
            f"- **Distancia**: {f'{dist:.1f} km' if dist is not None else '?'}",
            f"- **Estado selección**: {sel_status}",
        ]
        classif = result.climate.get("climate_classification") or {}
        if classif:
            koppen = classif.get("koppen_code", "?")
            koppen_desc = classif.get("koppen_description", "")
            martonne = classif.get("martonne_index")
            martonne_class = classif.get("martonne_class", "?")
            lines.append(f"- **Köppen**: {koppen} — {koppen_desc}")
            if martonne is not None:
                lines.append(f"- **Martonne**: {martonne:.1f} ({martonne_class})")
        climogram = result.climate.get("climogram_path")
        if climogram:
            lines.append(f"- **Climograma**: `{climogram}`")
    else:
        lines.append("No se completó el análisis climático.")
    lines.append("")

    # --- Cartografía ---
    lines.append("## Cartografía (CA-10 + CA-11)")
    lines.append("")
    if result.cartography_plan:
        maps = result.cartography_plan.get("maps", [])
        ready = result.cartography_plan.get("ready_for_render", False)
        center = result.cartography_plan.get("center", {})
        lines += [
            f"- **Mapas planificados**: {len(maps)}",
            f"- **Listo para renderizado**: {'Sí' if ready else 'No'}",
            f"- **Centro**: {center.get('lat', '?'):.5f}, {center.get('lon', '?'):.5f}"
            f" [{center.get('status', '?')}]",
            "",
            "| ID | Título | Extent | Estado |",
            "|----|--------|--------|--------|",
        ]
        for m in maps:
            lines.append(
                f"| {m.get('map_id', '?')} | {m.get('title', '?')} "
                f"| {m.get('extent_key', '?')} | {m.get('status', '?')} |"
            )
        lines.append("")
    else:
        lines += ["No se completó el plan cartográfico.", ""]

    # --- Mapas esquemáticos ---
    if result.schematic_maps:
        lines.append("### Mapas esquemáticos (CA-11)")
        lines.append("")
        generated = [m for m in result.schematic_maps
                     if m.get("status") == "GENERATED_PROVISIONAL"]
        if generated:
            lines.append(
                f"{len(generated)}/{len(result.schematic_maps)} mapas PNG generados "
                "(esquemáticos provisionales)."
            )
            lines.append("")
            lines.append("| ID | Título | Archivo | Estado |")
            lines.append("|----|--------|---------|--------|")
            for m in result.schematic_maps:
                fname = Path(m.get("output_path", "?")).name if m.get("output_path") else "?"
                lines.append(
                    f"| {m.get('map_id', '?')} | {m.get('title', '?')} "
                    f"| `{fname}` | {m.get('status', '?')} |"
                )
        else:
            lines.append("Mapas planificados (no generados — usar --write para generarlos).")
        lines.append("")

    # --- Warnings ---
    if result.warnings:
        lines += ["## Avisos", ""]
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # --- Notes ---
    if result.notes:
        lines += ["## Notas", ""]
        for n in result.notes:
            lines.append(f"- {n}")
        lines.append("")

    lines += [
        "---",
        "",
        "> **Fase 4 offline completa en modo test. "
        "No apta para presentación administrativa.**  ",
        "> La cartografía esquemática debe sustituirse por cartografía oficial "
        "(WMS/WMTS, Grafcan, IGN) antes de la presentación del Documento Ambiental.",
        "> El siguiente paso recomendado es la cartografía oficial (CA-12+) "
        "o el inventario ambiental (Fase 5).",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# run_phase4_offline
# ---------------------------------------------------------------------------

def run_phase4_offline(
    expediente_path: str | Path,
    stations_path: str | Path,
    climate_data_path: str | Path,
    phase2_result_path: str | Path | None = None,
    phase3_result_path: str | Path | None = None,
    write_outputs: bool = False,
    output_dir: str = "fase4",
) -> Phase4OfflineResult:
    """Pipeline integrador de Fase 4 offline.

    Ejecuta en orden:
      1. CA-08  — run_phase4_precheck
      2. CL-06  — run_phase4_climate
      3. CA-10  — build_cartography_plan
      4. CA-11  — generate_schematic_maps_from_plan (solo si write_outputs=True)

    Args:
        expediente_path:    Ruta al directorio del expediente.
        stations_path:      Ruta al JSON de estaciones climáticas.
        climate_data_path:  Ruta al JSON de datos climáticos mensuales.
        phase2_result_path: Ruta a phase2_result.json. Por defecto:
                            <expediente>/control_interno/phase2_result.json
        phase3_result_path: No usado actualmente (reservado).
        write_outputs:      Si True, escribe todos los outputs.
        output_dir:         Subdirectorio para el resumen de Fase 4 (por defecto "fase4").

    Returns:
        Phase4OfflineResult con estado de todos los sub-módulos.

    Raises:
        FileNotFoundError: Si stations_path o climate_data_path no existen.
        FileNotFoundError: Si phase2_result.json no existe (propagado desde CL-06).
        ValueError: Si las coordenadas no se pueden extraer.
    """
    from eia_agent.core.phase4_precheck import run_phase4_precheck
    from eia_agent.core.phase4_climate_pipeline import run_phase4_climate
    from eia_agent.core.cartography_plan import build_cartography_plan
    from eia_agent.core.schematic_map_generator import (
        generate_schematic_maps_from_plan,
        SchematicMapConfig,
    )

    exp_path = Path(expediente_path)
    expediente_id = exp_path.name
    warnings: list[str] = []
    notes: list[str] = []

    # Validar paths de entrada antes de iniciar
    stations = Path(stations_path)
    if not stations.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de estaciones: {stations}. "
            "Proporcione --stations con una ruta válida."
        )
    climate_data = Path(climate_data_path)
    if not climate_data.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de datos climáticos: {climate_data}. "
            "Proporcione --climate-data con una ruta válida."
        )

    # -----------------------------------------------------------------------
    # Paso 1: CA-08 — Precheck
    # -----------------------------------------------------------------------
    precheck_result = run_phase4_precheck(exp_path, write_outputs=False)
    precheck_dict = precheck_result.to_dict()
    precheck_ok = precheck_result.error_count() == 0
    if not precheck_ok:
        warnings.append(
            f"Precheck detectó {precheck_result.error_count()} error(es). "
            "Revisar antes de avanzar."
        )

    # -----------------------------------------------------------------------
    # Paso 2: CL-06 — Pipeline climático
    # -----------------------------------------------------------------------
    climate_dict: dict | None = None
    try:
        climate_result = run_phase4_climate(
            exp_path,
            phase2_result_path=phase2_result_path,
            stations_path=str(stations),
            climate_data_path=str(climate_data),
            write_outputs=write_outputs,
            output_dir="clima",
        )
        climate_dict = climate_result.to_dict()
        if climate_result.warnings:
            for w in climate_result.warnings:
                warnings.append(f"[Clima] {w}")
    except (FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        warnings.append(f"Pipeline climático no completado: {exc}")

    # -----------------------------------------------------------------------
    # Paso 3: CA-10 — Plan cartográfico
    # -----------------------------------------------------------------------
    cartography_plan_dict: dict | None = None
    cart_result = None
    try:
        cart_result = build_cartography_plan(
            exp_path,
            phase2_result_path=phase2_result_path,
            write_outputs=write_outputs,
            output_dir="cartografia",
        )
        cartography_plan_dict = cart_result.to_dict()
        if cart_result.warnings:
            for w in cart_result.warnings:
                warnings.append(f"[Cartografía] {w}")
    except (FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        warnings.append(f"Plan cartográfico no completado: {exc}")

    # -----------------------------------------------------------------------
    # Paso 4: CA-11 — Mapas esquemáticos
    # -----------------------------------------------------------------------
    schematic_maps: list[dict] = []
    if write_outputs and cart_result is not None:
        plan_path = exp_path / "cartografia" / "cartografia_plan.json"
        maps_dir = exp_path / "cartografia" / "mapas"
        try:
            smap_results = generate_schematic_maps_from_plan(
                plan_path, maps_dir, SchematicMapConfig()
            )
            schematic_maps = [r.to_dict() for r in smap_results]
            errors_in_maps = [r for r in smap_results if r.status == "ERROR"]
            if errors_in_maps:
                warnings.append(
                    f"{len(errors_in_maps)} mapa(s) esquemático(s) no se generaron correctamente."
                )
        except Exception as exc:
            warnings.append(f"Generación de mapas esquemáticos no completada: {exc}")
    elif cart_result is not None:
        # Sin escritura: usar MapSpec dicts del plan cartográfico
        schematic_maps = [m.to_dict() for m in cart_result.maps]

    # -----------------------------------------------------------------------
    # Determinar estados
    # -----------------------------------------------------------------------
    ready_for_phase5 = (
        precheck_ok
        and climate_dict is not None
        and cartography_plan_dict is not None
        and len(schematic_maps) >= 6
    )

    # administrative_ready siempre False en este pipeline
    administrative_ready = False

    notes.append(
        "Fase 4 offline completa en modo test. "
        "No apta para presentación administrativa."
    )

    result = Phase4OfflineResult(
        expediente_id=expediente_id,
        precheck=precheck_dict,
        climate=climate_dict,
        cartography_plan=cartography_plan_dict,
        schematic_maps=schematic_maps,
        ready_for_phase5=ready_for_phase5,
        administrative_ready=False,
        warnings=warnings,
        notes=notes,
    )

    # -----------------------------------------------------------------------
    # Escribir resumen de Fase 4
    # -----------------------------------------------------------------------
    if write_outputs:
        fase4_dir = exp_path / output_dir
        fase4_dir.mkdir(parents=True, exist_ok=True)

        json_path = fase4_dir / "phase4_result.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

        md_path = fase4_dir / "phase4_result.md"
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write(build_phase4_offline_markdown(result))

        result.notes.append(
            f"Resumen escrito en: {fase4_dir} (phase4_result.json, phase4_result.md)"
        )

    return result
