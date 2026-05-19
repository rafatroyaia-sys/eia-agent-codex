"""
climogram_generator -- CL-04
Generación de climograma PNG a partir de datos climáticos mensuales.

No llama a AEMET ni a ningún servicio externo.
No selecciona estaciones (CL-02).
No calcula Köppen ni Martonne (CL-03).
No inserta en DOCX (CL-05).
No escribe nada salvo llamada explícita a generate_climogram().

Uso:
    from eia_agent.core.climogram_generator import generate_climogram
    from eia_agent.core.climate_indices import MonthlyClimateData

    data = MonthlyClimateData(temperatures_c=[...], precipitations_mm=[...])
    result = generate_climogram(data, "clima/climograma.png")
    print(result.summary())
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless — sin ventanas
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from eia_agent.core.climate_indices import (
    MonthlyClimateData,
    gaussen_dry_months,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_MONTH_ABBR_ES = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Colores del climograma
_COLOR_TEMP = "#d62728"          # rojo intenso — curva de temperatura
_COLOR_PRECIP = "#1f77b4"        # azul — barras de precipitación
_COLOR_DRY_HATCH = "#f7b731"     # amarillo — sombreado meses secos
_ALPHA_PRECIP = 0.75
_ALPHA_DRY = 0.18


# ---------------------------------------------------------------------------
# ClimogramConfig
# ---------------------------------------------------------------------------

@dataclass
class ClimogramConfig:
    """Parámetros de configuración del climograma."""

    title: str | None = None
    subtitle: str | None = None
    width_inches: float = 10.0
    height_inches: float = 6.0
    dpi: int = 150
    show_gaussen: bool = True
    show_annual_summary: bool = True
    language: str = "es"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "width_inches": self.width_inches,
            "height_inches": self.height_inches,
            "dpi": self.dpi,
            "show_gaussen": self.show_gaussen,
            "show_annual_summary": self.show_annual_summary,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ClimogramConfig":
        return cls(
            title=data.get("title"),
            subtitle=data.get("subtitle"),
            width_inches=float(data.get("width_inches", 10.0)),
            height_inches=float(data.get("height_inches", 6.0)),
            dpi=int(data.get("dpi", 150)),
            show_gaussen=bool(data.get("show_gaussen", True)),
            show_annual_summary=bool(data.get("show_annual_summary", True)),
            language=str(data.get("language", "es")),
        )


# ---------------------------------------------------------------------------
# ClimogramResult
# ---------------------------------------------------------------------------

@dataclass
class ClimogramResult:
    """Metadatos del climograma generado."""

    output_path: str
    width_px: int
    height_px: int
    dpi: int
    station_id: str | None
    station_name: str | None
    period: str | None
    annual_temperature_c: float
    annual_precipitation_mm: float
    dry_months_gaussen: list[int]
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "output_path": self.output_path,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi": self.dpi,
            "station_id": self.station_id,
            "station_name": self.station_name,
            "period": self.period,
            "annual_temperature_c": self.annual_temperature_c,
            "annual_precipitation_mm": self.annual_precipitation_mm,
            "dry_months_gaussen": list(self.dry_months_gaussen),
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"Climograma: {self.output_path}",
            f"  Dimensiones: {self.width_px}×{self.height_px} px @ {self.dpi} dpi",
        ]
        if self.station_name:
            lines.append(f"  Estación    : {self.station_name}"
                         + (f" ({self.station_id})" if self.station_id else ""))
        if self.period:
            lines.append(f"  Periodo     : {self.period}")
        lines.append(
            f"  T anual     : {self.annual_temperature_c:.1f} °C  |  "
            f"P anual: {self.annual_precipitation_mm:.1f} mm"
        )
        if self.dry_months_gaussen:
            dry_str = ", ".join(str(m) for m in self.dry_months_gaussen)
            lines.append(f"  Meses secos : {dry_str}")
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_png(path: "str | Path") -> bool:
    """Comprueba que el archivo existe, tiene tamaño > 0 y es un PNG válido."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    with open(p, "rb") as f:
        header = f.read(8)
    return header == _PNG_SIGNATURE


def default_climogram_filename(
    station_id: str | None = None,
    period: str | None = None,
) -> str:
    """Devuelve un nombre de archivo seguro para el climograma.

    Ejemplos:
        default_climogram_filename() → "climograma.png"
        default_climogram_filename("C029O", "1981-2010") → "climograma_C029O_1981-2010.png"
    """
    parts = ["climograma"]
    if station_id:
        safe = re.sub(r"[^\w\-]", "_", str(station_id))
        parts.append(safe)
    if period:
        safe = re.sub(r"[^\w\-]", "_", str(period))
        parts.append(safe)
    return "_".join(parts) + ".png"


# ---------------------------------------------------------------------------
# _build_figure — lógica de renderizado pura
# ---------------------------------------------------------------------------

def _build_figure(
    data: MonthlyClimateData,
    config: ClimogramConfig,
) -> tuple[plt.Figure, int, int, list[int]]:
    """Construye la figura matplotlib del climograma.

    Returns:
        (fig, width_px, height_px, dry_months_1indexed)
    """
    T = data.temperatures_c
    P = data.precipitations_mm
    months = list(range(12))
    x = [m + 0.5 for m in months]  # centros de barras

    T_annual = data.annual_temperature()
    P_annual = data.annual_precipitation()
    dry_months = gaussen_dry_months(T, P) if config.show_gaussen else []

    fig, ax_p = plt.subplots(figsize=(config.width_inches, config.height_inches))

    # ── Barras de precipitación (eje izquierdo) ──────────────────────────────
    ax_p.bar(
        x, P,
        width=0.8,
        color=_COLOR_PRECIP,
        alpha=_ALPHA_PRECIP,
        label="Precipitación (mm)",
        zorder=2,
    )
    ax_p.set_xlabel("Mes", fontsize=11)
    ax_p.set_ylabel("Precipitación (mm)", color=_COLOR_PRECIP, fontsize=11)
    ax_p.tick_params(axis="y", labelcolor=_COLOR_PRECIP)
    ax_p.set_xlim(0, 12)
    ax_p.set_xticks([m + 0.5 for m in months])
    ax_p.set_xticklabels(_MONTH_ABBR_ES, fontsize=10)

    # eje P: mínimo 0, máximo = max(P) * 1.25, mínimo razonable de escala
    p_max = max(max(P) * 1.25, 30.0)
    ax_p.set_ylim(0, p_max)
    ax_p.yaxis.set_major_locator(mticker.MaxNLocator(nbins=6, integer=True))

    # ── Curva de temperatura (eje derecho) ───────────────────────────────────
    ax_t = ax_p.twinx()
    ax_t.plot(
        x, T,
        color=_COLOR_TEMP,
        linewidth=2.5,
        marker="o",
        markersize=5,
        label="Temperatura (°C)",
        zorder=3,
    )
    ax_t.set_ylabel("Temperatura (°C)", color=_COLOR_TEMP, fontsize=11)
    ax_t.tick_params(axis="y", labelcolor=_COLOR_TEMP)

    # Escala de temperatura: centrada con margen
    t_min, t_max = min(T), max(T)
    t_margin = max((t_max - t_min) * 0.3, 3.0)
    ax_t.set_ylim(t_min - t_margin, t_max + t_margin)

    # ── Sombreado de meses secos (Gaussen) ───────────────────────────────────
    if dry_months:
        for dm in dry_months:
            ax_p.axvspan(
                dm - 1, dm,
                color=_COLOR_DRY_HATCH,
                alpha=_ALPHA_DRY,
                zorder=1,
                label="_nolegend_",
            )
        # Un único parche en la leyenda
        from matplotlib.patches import Patch
        dry_patch = Patch(
            facecolor=_COLOR_DRY_HATCH,
            alpha=0.5,
            label="Mes seco (Gaussen: P≤2T)",
        )

    # ── Leyenda unificada ─────────────────────────────────────────────────────
    handles_p, labels_p = ax_p.get_legend_handles_labels()
    handles_t, labels_t = ax_t.get_legend_handles_labels()
    all_handles = handles_p + handles_t
    all_labels = labels_p + labels_t
    if dry_months and config.show_gaussen:
        all_handles.append(dry_patch)
        all_labels.append(dry_patch.get_label())
    ax_p.legend(all_handles, all_labels, loc="upper right", fontsize=9, framealpha=0.85)

    # ── Resumen anual ─────────────────────────────────────────────────────────
    if config.show_annual_summary:
        summary_text = (
            f"T media anual: {T_annual:.1f} °C   "
            f"P anual: {P_annual:.0f} mm"
        )
        ax_p.text(
            0.01, 0.98, summary_text,
            transform=ax_p.transAxes,
            fontsize=9,
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7),
        )

    # ── Título y subtítulo ────────────────────────────────────────────────────
    title_parts = []
    if config.title:
        title_parts.append(config.title)
    elif data.station_name:
        title_parts.append(f"Climograma — {data.station_name}")
        if data.station_id:
            title_parts[-1] += f" ({data.station_id})"
    else:
        title_parts.append("Climograma")

    if config.subtitle:
        title_parts.append(config.subtitle)
    elif data.period:
        title_parts.append(f"Periodo: {data.period}")

    if len(title_parts) == 2:
        fig.suptitle(title_parts[0], fontsize=13, fontweight="bold", y=0.98)
        ax_p.set_title(title_parts[1], fontsize=10, pad=4)
    else:
        fig.suptitle(title_parts[0], fontsize=13, fontweight="bold", y=0.98)

    fig.tight_layout(rect=[0, 0, 1, 0.95])

    width_px = int(config.width_inches * config.dpi)
    height_px = int(config.height_inches * config.dpi)

    return fig, width_px, height_px, dry_months


# ---------------------------------------------------------------------------
# generate_climogram
# ---------------------------------------------------------------------------

def generate_climogram(
    data: MonthlyClimateData,
    output_path: "str | Path",
    config: ClimogramConfig | None = None,
) -> ClimogramResult:
    """Genera un climograma PNG a partir de datos climáticos mensuales.

    Args:
        data:        Datos climáticos con 12 meses de temperatura y precipitación.
        output_path: Ruta de destino. Debe terminar en '.png'.
        config:      Configuración visual. Si None, usa ClimogramConfig().

    Returns:
        ClimogramResult con metadatos del archivo generado.

    Raises:
        ValueError: Si los datos son inválidos o output_path no termina en '.png'.
    """
    data.validate()

    out = Path(output_path)
    if out.suffix.lower() != ".png":
        raise ValueError(
            f"output_path debe terminar en '.png', recibido: '{out.suffix}'. "
            f"Ruta completa: {out}"
        )

    if config is None:
        config = ClimogramConfig()

    # Crear directorio si no existe
    out.parent.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    notes: list[str] = []

    if max(data.precipitations_mm) == 0:
        warnings.append(
            "Todos los valores de precipitación son 0 — el climograma puede no ser representativo."
        )

    fig, width_px, height_px, dry_months = _build_figure(data, config)

    try:
        fig.savefig(str(out), dpi=config.dpi, bbox_inches="tight", format="png")
    finally:
        plt.close(fig)

    return ClimogramResult(
        output_path=str(out),
        width_px=width_px,
        height_px=height_px,
        dpi=config.dpi,
        station_id=data.station_id,
        station_name=data.station_name,
        period=data.period,
        annual_temperature_c=round(data.annual_temperature(), 2),
        annual_precipitation_mm=round(data.annual_precipitation(), 1),
        dry_months_gaussen=dry_months,
        warnings=warnings,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# generate_climogram_from_dict
# ---------------------------------------------------------------------------

def generate_climogram_from_dict(
    data: dict,
    output_path: "str | Path",
    config: ClimogramConfig | None = None,
) -> ClimogramResult:
    """Genera un climograma a partir del dict serializado de MonthlyClimateData.

    Raises:
        ValueError: Si el dict no tiene las claves esperadas o los datos son inválidos.
        KeyError:   Si faltan claves obligatorias ('temperatures_c', 'precipitations_mm').
    """
    monthly = MonthlyClimateData.from_dict(data)
    return generate_climogram(monthly, output_path, config)
