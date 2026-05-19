"""
phase4_climate_pipeline -- CL-06
Pipeline climático de Fase 4 en modo seguro/offline.

Orquesta CL-02 (selector estación), CL-03 (Köppen+Martonne+Gaussen) y
CL-04 (climograma PNG) a partir de archivos locales/fixtures.

No llama a AEMET ni a ningún servicio externo.
No genera cartografía (eso es CA-02 a CA-05).
No inserta el climograma en DOCX (eso es CL-05).
No redacta el Bloque B completo (eso es AG-10).
No usa IA.
No escribe nada salvo write_outputs=True.

Uso:
    from eia_agent.core.phase4_climate_pipeline import run_phase4_climate

    result = run_phase4_climate(
        "expediente-EIA-2026-X",
        stations_path="config/estaciones.json",
        climate_data_path="config/datos_climaticos.json",
    )
    print(result.summary())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from eia_agent.core.climate_indices import MonthlyClimateData
from eia_agent.core.climate_station_selector import (
    ClimateStation,
    find_nearest_station,
    load_stations_from_json,
)

# ---------------------------------------------------------------------------
# Phase4ClimateResult
# ---------------------------------------------------------------------------

@dataclass
class Phase4ClimateResult:
    """Resultado del pipeline climático de Fase 4."""

    expediente_id: str
    selected_station: dict | None
    station_distance_km: float | None
    station_selection_status: str
    climate_classification: dict | None
    climogram_path: str | None
    description_md: str
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "expediente_id": self.expediente_id,
            "selected_station": self.selected_station,
            "station_distance_km": self.station_distance_km,
            "station_selection_status": self.station_selection_status,
            "climate_classification": self.climate_classification,
            "climogram_path": self.climogram_path,
            "description_md": self.description_md,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [f"Pipeline climático — Expediente: {self.expediente_id}"]
        if self.selected_station:
            name = self.selected_station.get("name", "?")
            sid = self.selected_station.get("station_id", "?")
            dist = (
                f"{self.station_distance_km:.1f} km"
                if self.station_distance_km is not None
                else "?"
            )
            lines.append(
                f"  Estación         : {name} ({sid}) — {dist} "
                f"[{self.station_selection_status}]"
            )
        else:
            lines.append(f"  Estación         : {self.station_selection_status}")

        if self.climate_classification:
            cc = self.climate_classification
            lines.append(
                f"  Köppen           : {cc.get('koppen_code', '?')} "
                f"— {cc.get('koppen_label', '?')}"
            )
            lines.append(
                f"  Martonne         : {cc.get('martonne_index', '?'):.2f} "
                f"— {cc.get('martonne_label', '?')}"
            )
            t = cc.get("annual_temperature_c", "?")
            p = cc.get("annual_precipitation_mm", "?")
            lines.append(f"  T anual / P anual: {t} °C / {p} mm")
            dry = cc.get("dry_months_gaussen", [])
            if dry:
                lines.append(f"  Meses secos      : {dry}")
        else:
            lines.append("  Clasificación    : no disponible (sin datos climáticos)")

        if self.climogram_path:
            lines.append(f"  Climograma       : {self.climogram_path}")

        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# load_monthly_climate_dataset
# ---------------------------------------------------------------------------

def load_monthly_climate_dataset(path: "str | Path") -> "dict[str, MonthlyClimateData]":
    """Carga un archivo JSON local de datos climáticos mensuales.

    Formato esperado (lista de objetos):
        [
          {
            "station_id": "C029O",
            "station_name": "Lanzarote Aeropuerto",   (opcional)
            "period": "1981-2010",                     (opcional)
            "temperatures_c": [ ... 12 valores ... ],
            "precipitations_mm": [ ... 12 valores ... ]
          },
          ...
        ]

    Returns:
        dict keyed by station_id → MonthlyClimateData.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError:        Si el JSON es inválido, no es lista, o los datos no son válidos.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo de datos climáticos no encontrado: {p}")

    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en {p}: {exc}") from exc

    if not isinstance(raw, list):
        raise ValueError(
            f"El archivo {p} debe contener una lista de objetos, "
            f"pero se encontró: {type(raw).__name__}"
        )

    dataset: dict[str, MonthlyClimateData] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Elemento {i} no es un objeto: {item!r}")
        if "station_id" not in item:
            raise ValueError(f"Elemento {i} carece del campo 'station_id'.")
        monthly = MonthlyClimateData.from_dict(item)
        monthly.validate()  # ValueError si faltan 12 meses
        dataset[item["station_id"]] = monthly

    return dataset


# ---------------------------------------------------------------------------
# extract_wgs84_from_phase2
# ---------------------------------------------------------------------------

def extract_wgs84_from_phase2(phase2_data: dict) -> "tuple[float, float]":
    """Extrae las coordenadas WGS84 (lat, lon) de un phase2_result cargado.

    Acepta los siguientes formatos en ``object_scope.coordenadas_wgs84``:
      - ["28.9773, -13.5395"]            — un string "lat, lon"
      - ["28.9773", "-13.5395"]          — dos strings separados
      - [{"lat": 28.9773, "lon": -13.5395}]  — un dict con claves lat/lon

    Raises:
        ValueError: Si no hay coordenadas o no se pueden parsear.
    """
    object_scope: dict = phase2_data.get("object_scope") or {}
    coords: list = object_scope.get("coordenadas_wgs84") or []

    if not coords:
        raise ValueError(
            "No se encontraron coordenadas WGS84 en 'object_scope.coordenadas_wgs84'. "
            "Ejecute Fase 2 y declare las coordenadas del emplazamiento."
        )

    first = coords[0]

    # Formato dict: [{"lat": ..., "lon": ...}]
    if isinstance(first, dict):
        try:
            lat = float(
                first.get("lat") or first.get("latitude") or first.get("latitud")
            )
            lon = float(
                first.get("lon") or first.get("longitude") or first.get("longitud")
            )
            return lat, lon
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"No se pudo parsear coordenada tipo dict: {first!r}. Error: {exc}"
            ) from exc

    # Formato string con coma: ["28.9773, -13.5395"]
    first_str = str(first).strip()
    if "," in first_str:
        parts = first_str.replace(" ", "").split(",")
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass

    # Formato dos strings separados: ["28.9773", "-13.5395"]
    if len(coords) >= 2:
        try:
            return float(str(coords[0]).strip()), float(str(coords[1]).strip())
        except ValueError:
            pass

    # Último intento: primer elemento solo
    try:
        lat = float(first_str)
        raise ValueError(
            f"Se encontró una latitud ({lat}) pero no una longitud en coordenadas_wgs84: {coords!r}. "
            "Se esperan ambas coordenadas."
        )
    except ValueError:
        pass

    raise ValueError(
        f"No se pudo extraer coordenadas WGS84 de: {coords!r}. "
        "Formatos aceptados: ['lat, lon'], ['lat', 'lon'], [{'lat': ..., 'lon': ...}]."
    )


# ---------------------------------------------------------------------------
# build_climate_description_md
# ---------------------------------------------------------------------------

def build_climate_description_md(result: Phase4ClimateResult) -> str:
    """Genera un texto markdown de descripción climática a partir del resultado."""
    lines = ["## Descripción climática — Fase 4 (modo gabinete/offline)", ""]

    # Estación
    if result.selected_station:
        name = result.selected_station.get("name", "Desconocida")
        sid = result.selected_station.get("station_id", "?")
        dist = (
            f"{result.station_distance_km:.1f} km"
            if result.station_distance_km is not None
            else "no calculada"
        )
        period = result.selected_station.get("period")  # puede no estar en la estación

        lines.append(f"**Estación climática de referencia**: {name} ({sid})")
        lines.append(f"**Distancia al emplazamiento**: {dist} [{result.station_selection_status}]")

        if result.station_selection_status == "LEJANA":
            lines.append(
                "> **AVISO**: La estación seleccionada está a más de 25 km del emplazamiento. "
                "Los datos climáticos deben interpretarse con cautela. "
                "Se recomienda valorar prospección de campo o estación alternativa."
            )
        lines.append("")
    else:
        lines.append("**Estación climática de referencia**: no disponible")
        lines.append("")

    # Datos climáticos
    if result.climate_classification:
        cc = result.climate_classification
        t = cc.get("annual_temperature_c", "?")
        p = cc.get("annual_precipitation_mm", "?")
        koppen = cc.get("koppen_code", "?")
        koppen_label = cc.get("koppen_label", "?")
        martonne = cc.get("martonne_index")
        martonne_label = cc.get("martonne_label", "?")
        dry = cc.get("dry_months_names") or []
        period = cc.get("period")  # no siempre presente en el dict de ClassificationResult

        # Periodo desde la estación (puede estar en selected_station o en el dataset)
        if result.selected_station:
            station_period = result.selected_station.get("period")
            if station_period:
                lines.append(f"**Periodo de referencia**: {station_period}")

        lines.append(f"**Temperatura media anual**: {t} °C")
        lines.append(f"**Precipitación anual**: {p} mm")
        lines.append("")
        lines.append(f"**Clasificación Köppen-Geiger**: `{koppen}` — {koppen_label}")
        if martonne is not None:
            lines.append(
                f"**Índice de Martonne**: {martonne:.1f} — {martonne_label}"
            )
        if dry:
            lines.append(f"**Meses secos (Gaussen P≤2T)**: {', '.join(dry)}")
        else:
            lines.append("**Meses secos (Gaussen P≤2T)**: ninguno")
        lines.append("")

        if cc.get("notes"):
            lines.append("**Notas de clasificación**:")
            for note in cc["notes"]:
                lines.append(f"- {note}")
            lines.append("")

    else:
        lines.append("**Datos climáticos**: no disponibles para la estación seleccionada.")
        lines.append("")

    # Aviso de modo gabinete
    lines.append(
        "> **Nota metodológica**: Este análisis climático se ha realizado en modo gabinete "
        "a partir de datos locales. No se ha efectuado prospección climática de campo. "
        "Los valores proceden de normales climatológicas de archivo."
    )
    lines.append("")

    # Climograma
    if result.climogram_path:
        lines.append(f"**Climograma**: `{result.climogram_path}`")
        lines.append("")

    # Advertencias
    for w in result.warnings:
        lines.append(f"> AVISO: {w}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# run_phase4_climate
# ---------------------------------------------------------------------------

def run_phase4_climate(
    expediente_path: "str | Path",
    phase2_result_path: "str | Path | None" = None,
    stations_path: "str | Path | None" = None,
    climate_data_path: "str | Path | None" = None,
    write_outputs: bool = False,
    output_dir: str = "clima",
) -> Phase4ClimateResult:
    """Ejecuta el pipeline climático de Fase 4 en modo seguro/offline.

    Args:
        expediente_path:    Directorio raíz del expediente.
        phase2_result_path: Ruta a phase2_result.json. Por defecto:
                            control_interno/phase2_result.json.
        stations_path:      Ruta a JSON local de estaciones climáticas.
        climate_data_path:  Ruta a JSON local de datos mensuales por estación.
        write_outputs:      Si True, escribe JSON, MD y PNG en output_dir.
        output_dir:         Subdirectorio de salida (relativo a expediente_path).

    Returns:
        Phase4ClimateResult con todos los metadatos del análisis.

    Raises:
        FileNotFoundError: Si phase2_result.json no existe.
        ValueError:        Si las coordenadas no se pueden extraer.
    """
    exp_path = Path(expediente_path)
    warnings: list[str] = []
    notes: list[str] = []

    # ── 1. Cargar phase2_result.json ─────────────────────────────────────────
    p2_path = (
        Path(phase2_result_path)
        if phase2_result_path is not None
        else exp_path / "control_interno" / "phase2_result.json"
    )
    if not p2_path.exists():
        raise FileNotFoundError(
            f"phase2_result.json no encontrado: {p2_path}. "
            "Ejecute Fase 2 antes del pipeline climático."
        )

    with open(p2_path, encoding="utf-8") as f:
        phase2_data = json.load(f)

    # ── 2. Extraer coordenadas WGS84 ─────────────────────────────────────────
    lat, lon = extract_wgs84_from_phase2(phase2_data)

    # ── 3. Cargar estaciones ─────────────────────────────────────────────────
    if stations_path is None:
        warnings.append(
            "stations_path no proporcionado — imposible seleccionar estación climática."
        )
        return Phase4ClimateResult(
            expediente_id=exp_path.name,
            selected_station=None,
            station_distance_km=None,
            station_selection_status="NO_DISPONIBLE",
            climate_classification=None,
            climogram_path=None,
            description_md="Sin archivo de estaciones. No se puede continuar el pipeline.",
            warnings=warnings,
            notes=notes,
        )

    stations = load_stations_from_json(stations_path)

    # ── 4. Seleccionar estación más próxima ──────────────────────────────────
    selection = find_nearest_station(lat, lon, stations)
    warnings.extend(selection.warnings)
    notes.extend(selection.notes)

    if selection.status == "NO_DISPONIBLE" or selection.selected is None:
        warnings.append("No se encontró ninguna estación climática candidata en el archivo.")
        return Phase4ClimateResult(
            expediente_id=exp_path.name,
            selected_station=None,
            station_distance_km=None,
            station_selection_status="NO_DISPONIBLE",
            climate_classification=None,
            climogram_path=None,
            description_md=build_climate_description_md(Phase4ClimateResult(
                expediente_id=exp_path.name,
                selected_station=None,
                station_distance_km=None,
                station_selection_status="NO_DISPONIBLE",
                climate_classification=None,
                climogram_path=None,
                description_md="",
                warnings=warnings,
                notes=notes,
            )),
            warnings=warnings,
            notes=notes,
        )

    if selection.status == "LEJANA":
        warnings.append(
            f"La estación '{selection.selected.name}' está a "
            f"{selection.distance_km:.1f} km (>25 km). "
            "Interpretar datos climáticos con cautela."
        )

    # ── 5. Cargar datos climáticos ────────────────────────────────────────────
    if climate_data_path is None:
        warnings.append(
            "climate_data_path no proporcionado — no se puede clasificar el clima."
        )
        result_early = Phase4ClimateResult(
            expediente_id=exp_path.name,
            selected_station=selection.selected.to_dict(),
            station_distance_km=selection.distance_km,
            station_selection_status=selection.status,
            climate_classification=None,
            climogram_path=None,
            description_md="",
            warnings=warnings,
            notes=notes,
        )
        result_early.description_md = build_climate_description_md(result_early)
        return result_early

    dataset = load_monthly_climate_dataset(climate_data_path)

    # ── 6. Localizar datos de la estación seleccionada ───────────────────────
    station_id = selection.selected.station_id
    if station_id not in dataset:
        warnings.append(
            f"No hay datos climáticos mensuales para la estación '{station_id}' "
            "en el dataset proporcionado. Añada los datos o use otro archivo."
        )
        result_no_data = Phase4ClimateResult(
            expediente_id=exp_path.name,
            selected_station=selection.selected.to_dict(),
            station_distance_km=selection.distance_km,
            station_selection_status=selection.status,
            climate_classification=None,
            climogram_path=None,
            description_md="",
            warnings=warnings,
            notes=notes,
        )
        result_no_data.description_md = build_climate_description_md(result_no_data)
        return result_no_data

    monthly_data = dataset[station_id]

    # ── 7. Clasificar clima ───────────────────────────────────────────────────
    from eia_agent.core.climate_indices import classify_climate
    classification = classify_climate(monthly_data)
    warnings.extend(classification.warnings)
    notes.extend(classification.notes)

    # ── 8. Generar climograma si write_outputs ────────────────────────────────
    climogram_path: str | None = None
    if write_outputs:
        out_dir = exp_path / output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            from eia_agent.core.climogram_generator import (
                default_climogram_filename,
                generate_climogram,
            )
            climo_filename = default_climogram_filename(station_id, monthly_data.period)
            climo_path = out_dir / climo_filename
            generate_climogram(monthly_data, str(climo_path))
            climogram_path = str(climo_path)
        except ImportError as _ie:
            warnings.append(
                f"Climograma no generado (dependencia no disponible): {_ie}"
            )

    # ── 9. Construir resultado ────────────────────────────────────────────────
    result = Phase4ClimateResult(
        expediente_id=exp_path.name,
        selected_station=selection.selected.to_dict(),
        station_distance_km=selection.distance_km,
        station_selection_status=selection.status,
        climate_classification=classification.to_dict(),
        climogram_path=climogram_path,
        description_md="",  # se rellena a continuación
        warnings=warnings,
        notes=notes,
    )
    result.description_md = build_climate_description_md(result)

    # ── 10. Escribir outputs opcionales ──────────────────────────────────────
    if write_outputs:
        out_dir = exp_path / output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        json_path = out_dir / "phase4_climate_result.json"
        json_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        md_path = out_dir / "descripcion_clima.md"
        md_path.write_text(result.description_md, encoding="utf-8")

        climo_name = Path(climogram_path).name if climogram_path else "sin-climograma"
        notes.append(
            f"Outputs escritos en: {out_dir} "
            f"(phase4_climate_result.json, descripcion_clima.md, {climo_name})"
        )

    return result
