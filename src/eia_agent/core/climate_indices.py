"""
climate_indices -- CL-03
Clasificación climática: Köppen-Geiger, Martonne, Gaussen.

No llama a AEMET ni a ningún servicio externo.
No selecciona estaciones (CL-02).
No genera gráficos (CL-04).
No calcula normales (CL-01 + AEMET).
No redacta el bloque climático definitivo.
No escribe archivos.

Uso:
    from eia_agent.core.climate_indices import (
        MonthlyClimateData, classify_climate,
    )
    data = MonthlyClimateData(temperatures_c=[...], precipitations_mm=[...])
    result = classify_climate(data)
    print(result.summary())
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_MONTH_NAMES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_KOPPEN_NOTE = (
    "Clasificación Köppen-Geiger calculada mediante implementación simplificada; "
    "revisar en expediente definitivo si el resultado es sensible al umbral."
)

# Hemisferio norte: verano = abr-sep (índices 0-based: 3-8)
_SUMMER_IDX = [3, 4, 5, 6, 7, 8]
_WINTER_IDX = [9, 10, 11, 0, 1, 2]


# ---------------------------------------------------------------------------
# MonthlyClimateData
# ---------------------------------------------------------------------------

@dataclass
class MonthlyClimateData:
    """Datos climáticos mensuales normalizados (12 meses)."""

    temperatures_c: list[float]
    precipitations_mm: list[float]
    station_id: str | None = None
    station_name: str | None = None
    period: str | None = None
    source: str | None = None

    def validate(self) -> None:
        if len(self.temperatures_c) != 12:
            raise ValueError(
                f"temperatures_c debe tener 12 valores, tiene {len(self.temperatures_c)}."
            )
        if len(self.precipitations_mm) != 12:
            raise ValueError(
                f"precipitations_mm debe tener 12 valores, tiene {len(self.precipitations_mm)}."
            )
        for i, t in enumerate(self.temperatures_c):
            if not isinstance(t, (int, float)):
                raise TypeError(f"temperatures_c[{i}] no es numérico: {t!r}")
        for i, p in enumerate(self.precipitations_mm):
            if not isinstance(p, (int, float)):
                raise TypeError(f"precipitations_mm[{i}] no es numérico: {p!r}")
            if p < 0:
                raise ValueError(
                    f"precipitations_mm[{i}] no puede ser negativo: {p}"
                )

    def annual_temperature(self) -> float:
        return sum(self.temperatures_c) / 12.0

    def annual_precipitation(self) -> float:
        return sum(self.precipitations_mm)

    def coldest_month_temp(self) -> float:
        return min(self.temperatures_c)

    def warmest_month_temp(self) -> float:
        return max(self.temperatures_c)

    def driest_month_precipitation(self) -> float:
        return min(self.precipitations_mm)

    def wettest_month_precipitation(self) -> float:
        return max(self.precipitations_mm)

    def to_dict(self) -> dict:
        return {
            "temperatures_c": list(self.temperatures_c),
            "precipitations_mm": list(self.precipitations_mm),
            "station_id": self.station_id,
            "station_name": self.station_name,
            "period": self.period,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MonthlyClimateData":
        return cls(
            temperatures_c=[float(x) for x in data["temperatures_c"]],
            precipitations_mm=[float(x) for x in data["precipitations_mm"]],
            station_id=data.get("station_id"),
            station_name=data.get("station_name"),
            period=data.get("period"),
            source=data.get("source"),
        )


# ---------------------------------------------------------------------------
# ClimateClassification
# ---------------------------------------------------------------------------

@dataclass
class ClimateClassification:
    """Resultado completo de la clasificación climática."""

    koppen_code: str
    koppen_label: str
    martonne_index: float
    martonne_label: str
    dry_months_gaussen: list[int]
    dry_months_names: list[str]
    annual_temperature_c: float
    annual_precipitation_mm: float
    notes: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "koppen_code": self.koppen_code,
            "koppen_label": self.koppen_label,
            "martonne_index": self.martonne_index,
            "martonne_label": self.martonne_label,
            "dry_months_gaussen": list(self.dry_months_gaussen),
            "dry_months_names": list(self.dry_months_names),
            "annual_temperature_c": self.annual_temperature_c,
            "annual_precipitation_mm": self.annual_precipitation_mm,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        lines = [
            f"Köppen: {self.koppen_code} — {self.koppen_label}",
            f"Martonne: {self.martonne_index:.1f} ({self.martonne_label})",
            f"T anual: {self.annual_temperature_c:.1f} °C  |  "
            f"P anual: {self.annual_precipitation_mm:.1f} mm",
        ]
        if self.dry_months_names:
            lines.append(
                f"Meses secos (Gaussen): {', '.join(self.dry_months_names)}"
            )
        else:
            lines.append("Meses secos (Gaussen): ninguno")
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Martonne
# ---------------------------------------------------------------------------

def martonne_index(
    annual_precipitation_mm: float, annual_temperature_c: float
) -> float:
    """Índice de aridez de Martonne: I = P / (T + 10).

    Raises:
        ValueError: si T + 10 <= 0 (T anual <= -10 °C).
    """
    denom = annual_temperature_c + 10.0
    if denom <= 0:
        raise ValueError(
            f"T + 10 = {denom:.2f} ≤ 0 — el índice de Martonne no está definido "
            f"para T anual ≤ -10 °C (T = {annual_temperature_c} °C)."
        )
    return annual_precipitation_mm / denom


def classify_martonne(index: float) -> str:
    """Clasifica el índice de Martonne en categoría de aridez."""
    if index < 5:
        return "árido extremo"
    if index < 10:
        return "árido"
    if index < 20:
        return "semiárido"
    if index < 30:
        return "subhúmedo"
    if index < 60:
        return "húmedo"
    return "muy húmedo"


# ---------------------------------------------------------------------------
# Gaussen
# ---------------------------------------------------------------------------

def gaussen_dry_months(
    temperatures_c: list[float],
    precipitations_mm: list[float],
) -> list[int]:
    """Detecta meses secos según el criterio de Walter-Gaussen: P ≤ 2·T.

    Returns:
        Índices 1-12 (enero=1) de los meses secos.
    """
    return [
        i + 1
        for i, (t, p) in enumerate(zip(temperatures_c, precipitations_mm))
        if p <= 2.0 * t
    ]


def month_names_es(month_numbers: list[int]) -> list[str]:
    """Convierte números de mes (1-12) a nombres en español."""
    return [_MONTH_NAMES_ES[m - 1] for m in month_numbers]


# ---------------------------------------------------------------------------
# Köppen — helpers internos
# ---------------------------------------------------------------------------

def _pth(
    T_annual: float, p_total: float, precipitations_mm: list[float]
) -> float:
    """Umbral de precipitación Pth para la detección del clima seco B."""
    if p_total <= 0:
        return 20.0 * T_annual
    p_summer = sum(precipitations_mm[i] for i in _SUMMER_IDX)
    p_winter = sum(precipitations_mm[i] for i in _WINTER_IDX)
    if p_summer / p_total >= 0.70:
        return 20.0 * T_annual + 280.0
    if p_winter / p_total >= 0.70:
        return 20.0 * T_annual
    return 20.0 * T_annual + 140.0


def _cd_season_suffix(data: MonthlyClimateData) -> str:
    """Sufijo de estación seca para grupos C y D (s / w / f)."""
    p_s = [data.precipitations_mm[i] for i in _SUMMER_IDX]
    p_w = [data.precipitations_mm[i] for i in _WINTER_IDX]

    p_dry_s = min(p_s)
    p_wet_w = max(p_w)
    p_dry_w = min(p_w)
    p_wet_s = max(p_s)

    # Verano seco: mes más seco de verano < 40 mm Y ≤ 1/3 del mes más lluvioso de invierno
    dry_summer = p_dry_s < 40 and p_dry_s * 3 <= p_wet_w
    # Invierno seco: mes más seco de invierno ≤ 1/10 del mes más lluvioso de verano
    dry_winter = p_wet_s > 0 and p_dry_w * 10 <= p_wet_s

    if dry_summer:
        return "s"
    if dry_winter:
        return "w"
    return "f"


def _cd_temp_suffix(T_warm: float, temperatures_c: list[float]) -> str:
    """Sufijo térmico para grupos C y D (a / b / c)."""
    if T_warm >= 22:
        return "a"
    if sum(1 for t in temperatures_c if t > 10) >= 4:
        return "b"
    return "c"


# ---------------------------------------------------------------------------
# Köppen — clasificación principal
# ---------------------------------------------------------------------------

_KOPPEN_LABELS: dict[str, str] = {
    "Af":  "Tropical lluvioso (Af)",
    "Am":  "Tropical monzónico (Am)",
    "Aw":  "Tropical de sabana (Aw)",
    "BWh": "Árido desértico cálido (BWh)",
    "BWk": "Árido desértico frío (BWk)",
    "BSh": "Árido estepario cálido (BSh)",
    "BSk": "Árido estepario frío (BSk)",
    "Csa": "Mediterráneo cálido (Csa)",
    "Csb": "Mediterráneo fresco (Csb)",
    "Csc": "Mediterráneo subpolar (Csc)",
    "Cfa": "Subtropical húmedo cálido (Cfa)",
    "Cfb": "Oceánico templado (Cfb)",
    "Cfc": "Oceánico subpolar (Cfc)",
    "Cwa": "Subtropical con invierno seco cálido (Cwa)",
    "Cwb": "Subtropical con invierno seco fresco (Cwb)",
    "Cwc": "Subtropical con invierno seco frío (Cwc)",
    "Dfa": "Continental húmedo cálido (Dfa)",
    "Dfb": "Continental húmedo fresco (Dfb)",
    "Dfc": "Continental subártico (Dfc)",
    "Dsa": "Continental seco de verano cálido (Dsa)",
    "Dsb": "Continental seco de verano fresco (Dsb)",
    "Dsc": "Continental seco de verano frío (Dsc)",
    "Dwa": "Continental con invierno seco cálido (Dwa)",
    "Dwb": "Continental con invierno seco fresco (Dwb)",
    "Dwc": "Continental con invierno seco frío (Dwc)",
    "ET":  "Tundra (ET)",
    "EF":  "Casquete de hielo / polar (EF)",
}


def classify_koppen(
    data: MonthlyClimateData,
) -> tuple[str, str, list[str]]:
    """Clasifica el clima según Köppen-Geiger (hemisferio norte).

    Returns:
        (codigo, etiqueta_es, notas)

    Note:
        Implementación simplificada para uso técnico en EIA.
        Revisar si el emplazamiento está cerca de umbrales de clasificación.
    """
    data.validate()

    T = data.annual_temperature()
    P = data.annual_precipitation()
    T_cold = data.coldest_month_temp()
    T_warm = data.warmest_month_temp()
    notes = [_KOPPEN_NOTE]

    # ── Polar E ──────────────────────────────────────────────────────────────
    if T_warm <= 10:
        code = "ET" if T_warm > 0 else "EF"
        return code, _KOPPEN_LABELS[code], notes

    # ── Seco B ───────────────────────────────────────────────────────────────
    Pth = _pth(T, P, data.precipitations_mm)
    if P < Pth:
        sfx = "h" if T >= 18 else "k"
        code = f"BW{sfx}" if P < 0.5 * Pth else f"BS{sfx}"
        return code, _KOPPEN_LABELS[code], notes

    # ── Tropical A ───────────────────────────────────────────────────────────
    if T_cold >= 18:
        p_dry = data.driest_month_precipitation()
        if p_dry >= 60:
            code = "Af"
        elif p_dry >= 100.0 - P / 25.0:
            code = "Am"
        else:
            code = "Aw"
        return code, _KOPPEN_LABELS[code], notes

    # ── Templado C ───────────────────────────────────────────────────────────
    if T_cold > -3 and T_warm > 10:
        sfx_s = _cd_season_suffix(data)
        sfx_t = _cd_temp_suffix(T_warm, data.temperatures_c)
        code = f"C{sfx_s}{sfx_t}"
        return code, _KOPPEN_LABELS.get(code, f"Templado ({code})"), notes

    # ── Continental D ────────────────────────────────────────────────────────
    if T_cold <= -3 and T_warm > 10:
        sfx_s = _cd_season_suffix(data)
        sfx_t = _cd_temp_suffix(T_warm, data.temperatures_c)
        code = f"D{sfx_s}{sfx_t}"
        return code, _KOPPEN_LABELS.get(code, f"Continental ({code})"), notes

    # ── Fallback ─────────────────────────────────────────────────────────────
    return (
        "?",
        "No determinado",
        notes + ["No se pudo asignar grupo Köppen con los datos disponibles."],
    )


# ---------------------------------------------------------------------------
# classify_climate
# ---------------------------------------------------------------------------

def classify_climate(data: MonthlyClimateData) -> ClimateClassification:
    """Clasifica el clima: Köppen, Martonne e índice de Gaussen.

    Args:
        data: Datos climáticos mensuales.

    Returns:
        ClimateClassification con todos los índices calculados.
    """
    data.validate()

    T_annual = data.annual_temperature()
    P_annual = data.annual_precipitation()

    koppen_code, koppen_label, koppen_notes = classify_koppen(data)

    warnings: list[str] = []
    try:
        m_idx = martonne_index(P_annual, T_annual)
        m_label = classify_martonne(m_idx)
    except ValueError as exc:
        m_idx = float("nan")
        m_label = "no calculable"
        warnings.append(str(exc))

    dry_months = gaussen_dry_months(data.temperatures_c, data.precipitations_mm)
    dry_names = month_names_es(dry_months)

    return ClimateClassification(
        koppen_code=koppen_code,
        koppen_label=koppen_label,
        martonne_index=round(m_idx, 2),
        martonne_label=m_label,
        dry_months_gaussen=dry_months,
        dry_months_names=dry_names,
        annual_temperature_c=round(T_annual, 2),
        annual_precipitation_mm=round(P_annual, 1),
        notes=koppen_notes,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# parse_monthly_climate_from_aemet_normals
# ---------------------------------------------------------------------------

def parse_monthly_climate_from_aemet_normals(
    raw: object,
    station_id: str | None = None,
    station_name: str | None = None,
) -> MonthlyClimateData:
    """Convierte datos de normales AEMET OpenData a MonthlyClimateData.

    Acepta dos formatos:

    1. Lista de 12 dicts con claves 'mes', 'tm_mes', 'pr_mes'
       (respuesta directa de AEMET OpenData).
       El registro anual ('mes'='Año' o '13') se ignora si está presente.

    2. Dict con claves 'temperatures_c' y 'precipitations_mm'
       (formato interno del proyecto).

    Limitaciones:
        - Solo extrae temperatura media mensual (tm_mes) y precipitación (pr_mes).
        - No valida la calidad de los datos ni el periodo de referencia.
        - No cubre todos los formatos posibles de AEMET.

    Raises:
        ValueError: Si el formato no es reconocible, faltan meses o campos.
    """
    # Formato 2: dict interno
    if isinstance(raw, dict):
        if "temperatures_c" in raw and "precipitations_mm" in raw:
            result = MonthlyClimateData.from_dict(raw)
            if station_id:
                result.station_id = station_id
            if station_name:
                result.station_name = station_name
            return result
        raise ValueError(
            "Dict no reconocido: se esperan claves 'temperatures_c' y "
            "'precipitations_mm', o una lista de registros AEMET."
        )

    # Formato 1: lista de registros mensuales AEMET
    if not isinstance(raw, list):
        raise ValueError(
            f"Formato no reconocido: se esperaba lista de dicts mensuales o "
            f"dict interno. Tipo recibido: {type(raw).__name__}."
        )

    monthly = [
        r for r in raw
        if isinstance(r, dict)
        and str(r.get("mes", "")).strip() not in ("", "Año", "13")
    ]

    if len(monthly) != 12:
        raise ValueError(
            f"Se esperan exactamente 12 registros mensuales; "
            f"se encontraron {len(monthly)}."
        )

    try:
        monthly = sorted(monthly, key=lambda r: int(str(r["mes"]).strip()))
    except (KeyError, ValueError) as exc:
        raise ValueError(f"No se pudo ordenar por 'mes': {exc}") from exc

    temperatures_c: list[float] = []
    precipitations_mm: list[float] = []
    period: str | None = None

    for r in monthly:
        mes = r.get("mes")

        tm = r.get("tm_mes")
        if tm is None:
            raise ValueError(
                f"Registro del mes {mes} sin campo 'tm_mes' "
                "(temperatura media mensual)."
            )
        try:
            temperatures_c.append(float(str(tm).replace(",", ".")))
        except ValueError as exc:
            raise ValueError(
                f"'tm_mes' no numérico en mes {mes}: {tm!r}"
            ) from exc

        pr = r.get("pr_mes")
        if pr is None:
            raise ValueError(
                f"Registro del mes {mes} sin campo 'pr_mes' "
                "(precipitación media mensual)."
            )
        try:
            precipitations_mm.append(float(str(pr).replace(",", ".")))
        except ValueError as exc:
            raise ValueError(
                f"'pr_mes' no numérico en mes {mes}: {pr!r}"
            ) from exc

        if period is None:
            period = r.get("periodo")

    if station_id is None:
        for key in ("indicativo", "indsinop", "station_id"):
            val = monthly[0].get(key)
            if val is not None:
                station_id = str(val)
                break

    if station_name is None:
        val = monthly[0].get("nombre") or monthly[0].get("name")
        if val is not None:
            station_name = str(val)

    return MonthlyClimateData(
        temperatures_c=temperatures_c,
        precipitations_mm=precipitations_mm,
        station_id=station_id,
        station_name=station_name,
        period=period,
        source="AEMET OpenData",
    )
