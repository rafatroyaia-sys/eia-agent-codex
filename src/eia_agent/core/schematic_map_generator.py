"""
schematic_map_generator -- CA-11
Generador de mapas esquemáticos offline para Fase 4 EIA.

Produce PNGs provisionales a partir de un CartographyPlanResult (CA-10).
No usa tiles reales, no llama a APIs externas, no genera cartografía oficial.

Los PNGs generados incluyen sello PROVISIONAL y no son aptos para
presentación administrativa.

Uso:
    from eia_agent.core.schematic_map_generator import (
        generate_schematic_map, generate_schematic_maps_from_plan,
        SchematicMapConfig, validate_png,
    )

    config = SchematicMapConfig()
    result = generate_schematic_map(map_spec, "cartografia/mapas/MAP-001.png", config)
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_TITLE_H = 72
_LEGEND_W = 316
_BOTTOM_H = 88
_PAD = 8

# ---------------------------------------------------------------------------
# Color palette (RGB or RGBA tuples)
# ---------------------------------------------------------------------------
_C: dict = {
    "page":        (234, 239, 245),
    "title_bg":    (24,  54,  92 ),
    "title_fg":    (255, 255, 255),
    "badge_fg":    (255, 230,  60),
    "map_bg":      (208, 226, 241),
    "grid":        (168, 194, 214),
    "ext_border":  (72,  116, 158),
    "marker":      (204,  30,   0),
    "marker_lgt":  (255,  90,  50),
    "north":       (24,   54,  92),
    "scale_fg":    (28,   28,  28),
    "leg_bg":      (245, 248, 251),
    "leg_border":  (160, 178, 194),
    "bot_bg":      (34,   52,  70),
    "bot_fg":      (208, 224, 240),
    "warn_fg":     (255, 232,  60),
    "txt_dk":      (22,   30,  42),
    "txt_md":      (78,   92, 108),
    "txt_lt":      (128, 144, 160),
    "wmark":       (188,   0,   0,  48),
}


# ---------------------------------------------------------------------------
# Font loader
# ---------------------------------------------------------------------------
def _font(size: int) -> ImageFont.ImageFont:
    """Return best available font at given pixel size."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        pass
    for path in [
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size=size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def _tw(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    try:
        bb = draw.textbbox((0, 0), text, font=fnt)
        return max(1, bb[2] - bb[0])
    except Exception:
        return len(text) * 7


def _th(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    try:
        bb = draw.textbbox((0, 0), text, font=fnt)
        return max(1, bb[3] - bb[1])
    except Exception:
        return 12


def _text_c(draw: ImageDraw.ImageDraw, cx: int, y: int, text: str, fnt, fill):
    """Draw text centered at cx."""
    try:
        draw.text((cx, y), text, fill=fill, font=fnt, anchor="mt")
    except Exception:
        w = _tw(draw, text, fnt)
        draw.text((cx - w // 2, y), text, fill=fill, font=fnt)


def _text_r(draw: ImageDraw.ImageDraw, rx: int, y: int, text: str, fnt, fill):
    """Draw text right-aligned at rx."""
    try:
        draw.text((rx, y), text, fill=fill, font=fnt, anchor="rt")
    except Exception:
        w = _tw(draw, text, fnt)
        draw.text((rx - w, y), text, fill=fill, font=fnt)


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------------------------------------------------------------------------
# Scale helpers
# ---------------------------------------------------------------------------
_NICE = [10, 20, 50, 100, 150, 200, 250, 500, 750, 1000, 1500, 2000, 2500,
         5000, 7500, 10_000, 15_000, 20_000, 25_000, 50_000]


def _nice_scale(radius_m: float, canvas_px: int) -> tuple[float, int]:
    """Return (nice_m, bar_px) for a scale bar ~1/6 canvas width."""
    m_per_px = (2.0 * radius_m) / max(canvas_px, 1)
    target_m = (canvas_px // 6) * m_per_px
    chosen = min(_NICE, key=lambda v: abs(v - target_m))
    bar_px = max(30, min(int(round(chosen / m_per_px)), canvas_px // 3))
    return float(chosen), bar_px


def _fmt_dist(m: float) -> str:
    if m >= 1000:
        return f"{m / 1000:g} km"
    return f"{m:g} m"


# ---------------------------------------------------------------------------
# Drawing sub-routines
# ---------------------------------------------------------------------------

def _draw_title(draw: ImageDraw.ImageDraw, W: int, H_t: int,
                map_id: str, title: str, extent_key: str,
                f_lg, f_sm):
    draw.rectangle([0, 0, W, H_t], fill=_C["title_bg"])
    draw.text((14, 10), f"{map_id}  ·  {extent_key}", fill=_C["title_fg"], font=f_sm)
    draw.text((14, 32), _trunc(title, 60), fill=_C["title_fg"], font=f_lg)
    badge = "◼ PROVISIONAL — MODO TEST"
    _text_r(draw, W - 12, 30, badge, f_sm, _C["badge_fg"])


def _draw_map_area(draw: ImageDraw.ImageDraw,
                   mx: int, my: int, mw: int, mh: int,
                   clat: float, clon: float, radius_m: float, bbox: dict,
                   f_md, f_sm, f_xs):
    # Background + border
    draw.rectangle([mx, my, mx + mw, my + mh],
                   fill=_C["map_bg"], outline=_C["ext_border"], width=2)

    # Grid (3×3 internal cells → 2 lines each direction)
    for i in (1, 2, 3):
        gx = mx + (mw * i) // 4
        gy = my + (mh * i) // 4
        draw.line([gx, my + 1, gx, my + mh - 1], fill=_C["grid"], width=1)
        draw.line([mx + 1, gy, mx + mw - 1, gy], fill=_C["grid"], width=1)

    # Coordinate tick labels
    lat_range = bbox.get("max_lat", clat + 0.01) - bbox.get("min_lat", clat - 0.01)
    lon_range = bbox.get("max_lon", clon + 0.01) - bbox.get("min_lon", clon - 0.01)
    for i in (1, 2, 3):
        lon_v = bbox.get("min_lon", clon - lon_range / 2) + lon_range * i / 4
        lat_v = bbox.get("max_lat", clat + lat_range / 2) - lat_range * i / 4
        gx = mx + (mw * i) // 4
        gy = my + (mh * i) // 4
        try:
            draw.text((gx, my + mh - 2), f"{lon_v:.4f}°",
                      fill=_C["txt_md"], font=f_xs, anchor="mb")
            draw.text((mx + 3, gy), f"{lat_v:.4f}°",
                      fill=_C["txt_md"], font=f_xs)
        except Exception:
            pass

    # Cardinal labels
    cx = mx + mw // 2
    cy = my + mh // 2
    for text, px, py, anch in [
        ("N", cx, my + 4, "mt"),
        ("S", cx, my + mh - 4, "mb"),
        ("O", mx + 4, cy, "lm"),
        ("E", mx + mw - 4, cy, "rm"),
    ]:
        try:
            draw.text((px, py), text, fill=_C["north"], font=f_sm, anchor=anch)
        except Exception:
            draw.text((px, py), text, fill=_C["north"], font=f_sm)

    # Center crosshair
    r = 20
    draw.line([cx - r, cy, cx + r, cy], fill=_C["marker"], width=3)
    draw.line([cx, cy - r, cx, cy + r], fill=_C["marker"], width=3)
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12],
                 outline=_C["marker"], width=3)
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=_C["marker"])
    try:
        draw.text((cx, cy + 16), "PROYECTO",
                  fill=_C["marker"], font=f_xs, anchor="mt")
    except Exception:
        draw.text((cx - 25, cy + 16), "PROYECTO", fill=_C["marker"], font=f_xs)

    # North arrow (top-right of map area)
    _draw_north_arrow(draw, mx + mw - 52, my + 16, f_sm)

    # Scale bar
    nice_m, bar_px = _nice_scale(radius_m, mw)
    _draw_scale_bar(draw, mx, my, mw, mh, nice_m, bar_px, f_sm, f_xs)


def _draw_north_arrow(draw: ImageDraw.ImageDraw, nx: int, ny: int, fnt):
    tip = (nx, ny)
    bl, br = (nx - 11, ny + 34), (nx + 11, ny + 34)
    draw.polygon([tip, bl, br], fill=_C["north"])
    draw.line([nx, ny + 34, nx, ny + 46], fill=_C["north"], width=2)
    try:
        draw.text((nx, ny + 50), "N", fill=_C["north"], font=fnt, anchor="mt")
    except Exception:
        draw.text((nx - 5, ny + 50), "N", fill=_C["north"], font=fnt)


def _draw_scale_bar(draw: ImageDraw.ImageDraw,
                    mx: int, my: int, mw: int, mh: int,
                    nice_m: float, bar_px: int, f_sm, f_xs):
    sx = mx + (mw - bar_px) // 2
    sy = my + mh - 48
    bh = 8
    # Half: dark / light segments
    draw.rectangle([sx, sy, sx + bar_px // 2, sy + bh], fill=_C["scale_fg"])
    draw.rectangle([sx + bar_px // 2, sy, sx + bar_px, sy + bh],
                   fill=_C["leg_bg"], outline=_C["scale_fg"], width=1)
    # End ticks
    for tx in (sx, sx + bar_px // 2, sx + bar_px):
        draw.line([tx, sy - 5, tx, sy + bh + 5], fill=_C["scale_fg"], width=2)
    # Labels
    labels = [("0", sx), (_fmt_dist(nice_m / 2), sx + bar_px // 2),
              (_fmt_dist(nice_m), sx + bar_px)]
    for lbl, lx in labels:
        try:
            draw.text((lx, sy - 7), lbl, fill=_C["scale_fg"], font=f_xs, anchor="mb")
        except Exception:
            draw.text((lx, sy - 10), lbl, fill=_C["scale_fg"], font=f_xs)
    # Scale denominator
    dpi_factor = 39.37  # inches per meter * 100 (approx for 150 dpi)
    approx_denom = int((nice_m * 150 * dpi_factor) / bar_px)
    scale_lbl = f"Escala aprox. 1:{approx_denom:,}".replace(",", ".")
    try:
        _text_c(draw, sx + bar_px // 2, sy + bh + 6, scale_lbl, f_xs, _C["txt_md"])
    except Exception:
        draw.text((sx, sy + bh + 6), scale_lbl, fill=_C["txt_md"], font=f_xs)


def _draw_legend(draw: ImageDraw.ImageDraw,
                 lx: int, ly: int, lw: int, lh: int,
                 layers: list[str], sources: list[str],
                 clat: float, clon: float, cstatus: str, radius_m: float,
                 f_md, f_sm, f_xs):
    draw.rectangle([lx, ly, lx + lw, ly + lh],
                   fill=_C["leg_bg"], outline=_C["leg_border"], width=1)
    pad = 10
    y = ly + 12
    line_h_md = _th(draw, "X", f_md) + 2
    line_h_sm = _th(draw, "X", f_sm) + 3
    line_h_xs = _th(draw, "X", f_xs) + 4

    def _sep():
        nonlocal y
        y += 4
        draw.line([lx + pad, y, lx + lw - pad, y], fill=_C["leg_border"], width=1)
        y += 8

    # Title
    draw.text((lx + pad, y), "LEYENDA", fill=_C["title_bg"], font=f_md)
    y += line_h_md + 4
    _sep()

    # Required layers
    draw.text((lx + pad, y), "Capas requeridas:", fill=_C["txt_dk"], font=f_sm)
    y += line_h_sm
    for layer in layers[:8]:
        dot_y = y + line_h_xs // 2
        draw.ellipse([lx + pad + 2, dot_y - 4, lx + pad + 10, dot_y + 4],
                     fill=_C["title_bg"])
        draw.text((lx + pad + 16, y), _trunc(layer, 24),
                  fill=_C["txt_dk"], font=f_xs)
        y += line_h_xs
    _sep()

    # Sources
    draw.text((lx + pad, y), "Fuentes candidatas:", fill=_C["txt_dk"], font=f_sm)
    y += line_h_sm
    for src in sources[:4]:
        draw.text((lx + pad + 4, y), f"› {_trunc(src, 28)}",
                  fill=_C["txt_md"], font=f_xs)
        y += line_h_xs
    _sep()

    # Coordinates
    draw.text((lx + pad, y), "Centro:", fill=_C["txt_dk"], font=f_sm)
    y += line_h_sm
    draw.text((lx + pad + 4, y), f"Lat: {clat:.5f}°", fill=_C["txt_dk"], font=f_xs)
    y += line_h_xs
    draw.text((lx + pad + 4, y), f"Lon: {clon:.5f}°", fill=_C["txt_dk"], font=f_xs)
    y += line_h_xs
    draw.text((lx + pad + 4, y), f"Estado: {cstatus}", fill=_C["txt_md"], font=f_xs)
    y += line_h_xs
    _sep()

    # Radius
    draw.text((lx + pad, y), "Extensión:", fill=_C["txt_dk"], font=f_sm)
    y += line_h_sm
    draw.text((lx + pad + 4, y), f"Radio: {_fmt_dist(radius_m)}", fill=_C["txt_dk"], font=f_xs)
    y += line_h_xs
    draw.text((lx + pad + 4, y), f"Ancho total: {_fmt_dist(radius_m * 2)}", fill=_C["txt_md"], font=f_xs)

    # Marker legend (bottom of panel)
    marker_y = ly + lh - 68
    if marker_y > y + 20:
        draw.line([lx + pad, marker_y - 6, lx + lw - pad, marker_y - 6],
                  fill=_C["leg_border"], width=1)
        draw.ellipse([lx + pad + 2, marker_y + 4, lx + pad + 14, marker_y + 16],
                     outline=_C["marker"], width=2)
        draw.line([lx + pad + 2, marker_y + 10, lx + pad + 14, marker_y + 10],
                  fill=_C["marker"], width=2)
        draw.line([lx + pad + 8, marker_y + 4, lx + pad + 8, marker_y + 16],
                  fill=_C["marker"], width=2)
        draw.text((lx + pad + 20, marker_y + 3), "Punto del proyecto",
                  fill=_C["txt_dk"], font=f_xs)


def _draw_bottom(draw: ImageDraw.ImageDraw,
                 W: int, bot_y: int, bot_h: int,
                 source: str, map_status: str, f_sm, f_xs):
    draw.rectangle([0, bot_y, W, bot_y + bot_h], fill=_C["bot_bg"])
    mid = bot_y + bot_h // 2
    # Left: source
    draw.text((14, mid - 14), "FUENTE:", fill=_C["bot_fg"], font=f_xs)
    draw.text((14, mid + 0), _trunc(source, 48), fill=_C["bot_fg"], font=f_xs)
    # Center: disclaimer
    disc = "Mapa esquemático provisional. No sustituye cartografía oficial WMS/WMTS."
    _text_c(draw, W // 2, mid - 8, disc, f_xs, _C["warn_fg"])
    # Right: status
    _text_r(draw, W - 14, mid - 14, "SIN DATOS REALES", f_xs, _C["warn_fg"])
    _text_r(draw, W - 14, mid + 0, f"Estado: {map_status}", f_xs, _C["bot_fg"])


def _apply_watermark(img: Image.Image, text: str) -> Image.Image:
    """Overlay a diagonal tiled watermark on the image."""
    W, H = img.size
    fnt = _font(64)
    # Measure text on a dummy surface
    dummy_img = Image.new("RGBA", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    try:
        bb = dummy_draw.textbbox((0, 0), text, font=fnt)
        tw, th = bb[2] - bb[0] + 20, bb[3] - bb[1] + 20
    except Exception:
        tw, th = 600, 80

    # Create single text tile
    tile = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    td = ImageDraw.Draw(tile)
    td.text((10, 10), text, font=fnt, fill=_C["wmark"])
    rotated = tile.rotate(40, expand=True, fillcolor=(0, 0, 0, 0))
    rw, rh = rotated.size

    # Build tiled overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    step_x = rw + 80
    step_y = rh + 60
    for px in range(-rw, W + rw, step_x):
        for py in range(-rh, H + rh, step_y):
            overlay.paste(rotated, (px, py), rotated)

    result = img.convert("RGBA")
    result = Image.alpha_composite(result, overlay)
    return result.convert("RGB")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SchematicMapConfig:
    """Configuración para la generación de mapas esquemáticos."""
    width_px: int = 1600
    height_px: int = 1100
    dpi: int = 150
    show_test_watermark: bool = True
    background: str = "light"
    language: str = "es"

    def to_dict(self) -> dict:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi": self.dpi,
            "show_test_watermark": self.show_test_watermark,
            "background": self.background,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SchematicMapConfig":
        return cls(
            width_px=int(data.get("width_px", 1600)),
            height_px=int(data.get("height_px", 1100)),
            dpi=int(data.get("dpi", 150)),
            show_test_watermark=bool(data.get("show_test_watermark", True)),
            background=str(data.get("background", "light")),
            language=str(data.get("language", "es")),
        )


@dataclass
class SchematicMapResult:
    """Resultado de la generación de un mapa esquemático."""
    map_id: str
    title: str
    output_path: str
    width_px: int
    height_px: int
    status: str  # GENERATED_PROVISIONAL | ERROR
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "map_id": self.map_id,
            "title": self.title,
            "output_path": self.output_path,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "status": self.status,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        lines = [
            f"{self.map_id} — {self.title} [{self.status}]",
            f"  Archivo : {self.output_path}",
            f"  Tamaño  : {self.width_px}×{self.height_px}px",
        ]
        for w in self.warnings:
            lines.append(f"  AVISO: {w}")
        for n in self.notes:
            lines.append(f"  Nota: {n}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# validate_png
# ---------------------------------------------------------------------------

def validate_png(path: str | Path) -> bool:
    """Devuelve True si el archivo existe, no está vacío y tiene firma PNG."""
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        with open(p, "rb") as fh:
            header = fh.read(8)
        return header == _PNG_SIGNATURE
    except OSError:
        return False


# ---------------------------------------------------------------------------
# load_cartography_plan
# ---------------------------------------------------------------------------

def load_cartography_plan(path: str | Path) -> dict:
    """Carga un cartografia_plan.json y valida su estructura mínima.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el JSON es inválido o no contiene lista de mapas.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Plan cartográfico no encontrado: {p}. "
            "Ejecute CA-10 (cartography-plan) antes de generar mapas esquemáticos."
        )
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON inválido en '{p}': {exc}") from exc
    if "maps" not in data or not isinstance(data["maps"], list):
        raise ValueError(
            f"El archivo '{p}' no contiene una lista 'maps' válida. "
            "Verifique que fue generado por CA-10."
        )
    return data


# ---------------------------------------------------------------------------
# generate_schematic_map
# ---------------------------------------------------------------------------

def _spec_to_dict(spec) -> dict:
    """Normaliza MapSpec o dict a dict."""
    if isinstance(spec, dict):
        return spec
    try:
        return spec.to_dict()
    except AttributeError:
        return dict(spec)


def generate_schematic_map(
    map_spec,
    output_path: str | Path,
    config: SchematicMapConfig | None = None,
) -> SchematicMapResult:
    """Genera un PNG esquemático provisional para un MapSpec.

    Args:
        map_spec:    MapSpec (CA-10) o dict compatible.
        output_path: Ruta de salida. Debe terminar en .png.
        config:      Configuración del mapa. Por defecto SchematicMapConfig().

    Returns:
        SchematicMapResult con status GENERATED_PROVISIONAL o ERROR.

    Raises:
        ValueError: Si output_path no termina en .png.
    """
    if config is None:
        config = SchematicMapConfig()

    out = Path(output_path)
    if out.suffix.lower() != ".png":
        raise ValueError(
            f"output_path debe terminar en .png, recibido: '{output_path}'"
        )

    spec = _spec_to_dict(map_spec)
    map_id = spec.get("map_id", "MAP-???")
    title = spec.get("title", "Mapa sin título")
    extent_key = spec.get("extent_key", "")
    map_type = spec.get("map_type", "")
    layers = list(spec.get("required_layers") or [])
    sources = list(spec.get("source_candidates") or [])
    map_status = spec.get("status", "PLANNED")
    spec_warnings = list(spec.get("warnings") or [])

    extent = spec.get("extent") or {}
    center = extent.get("center") or {}
    bbox = extent.get("bbox") or {}
    radius_m = float(extent.get("radius_m") or 1000.0)
    clat = float(center.get("lat") or 0.0)
    clon = float(center.get("lon") or 0.0)
    cstatus = str(center.get("status") or "DECLARADO")
    src_first = sources[0] if sources else "No especificada"

    warnings: list[str] = [
        "Mapa esquemático provisional generado por CA-11. "
        "No contiene datos reales de WMS/WMTS ni cartografía oficial."
    ]
    notes: list[str] = []

    try:
        out.parent.mkdir(parents=True, exist_ok=True)

        W, H = config.width_px, config.height_px

        map_x = _PAD
        map_y = _TITLE_H + _PAD
        map_w = W - _LEGEND_W - _PAD * 3
        map_h = H - _TITLE_H - _BOTTOM_H - _PAD * 2
        leg_x = map_x + map_w + _PAD
        leg_w = W - leg_x - _PAD
        bot_y = map_y + map_h + _PAD

        img = Image.new("RGB", (W, H), _C["page"])
        draw = ImageDraw.Draw(img)

        f_xl = _font(22)
        f_lg = _font(18)
        f_md = _font(14)
        f_sm = _font(11)
        f_xs = _font(9)

        _draw_title(draw, W, _TITLE_H, map_id, title, extent_key, f_lg, f_sm)
        _draw_map_area(draw, map_x, map_y, map_w, map_h,
                       clat, clon, radius_m, bbox, f_md, f_sm, f_xs)
        _draw_legend(draw, leg_x, map_y, leg_w, map_h,
                     layers, sources, clat, clon, cstatus, radius_m,
                     f_md, f_sm, f_xs)
        _draw_bottom(draw, W, bot_y, _BOTTOM_H, src_first, map_status, f_sm, f_xs)

        if config.show_test_watermark:
            img = _apply_watermark(img, "PROVISIONAL — MODO TEST")

        img.save(str(out), format="PNG", dpi=(config.dpi, config.dpi))
        notes.append(f"PNG guardado en: {out}")

        return SchematicMapResult(
            map_id=map_id,
            title=title,
            output_path=str(out),
            width_px=W,
            height_px=H,
            status="GENERATED_PROVISIONAL",
            warnings=warnings,
            notes=notes,
        )

    except Exception as exc:
        return SchematicMapResult(
            map_id=map_id,
            title=title,
            output_path=str(out),
            width_px=config.width_px,
            height_px=config.height_px,
            status="ERROR",
            warnings=warnings + [f"Error al generar PNG: {exc}"],
            notes=notes,
        )


# ---------------------------------------------------------------------------
# generate_schematic_maps_from_plan
# ---------------------------------------------------------------------------

def generate_schematic_maps_from_plan(
    plan_path: str | Path,
    output_dir: str | Path,
    config: SchematicMapConfig | None = None,
) -> list[SchematicMapResult]:
    """Genera un PNG esquemático por cada mapa del plan cartográfico.

    Args:
        plan_path:  Ruta a cartografia_plan.json (generado por CA-10).
        output_dir: Directorio de salida para los PNGs.
        config:     Configuración compartida. Por defecto SchematicMapConfig().

    Returns:
        Lista de SchematicMapResult, uno por cada mapa del plan.

    Raises:
        FileNotFoundError: Si plan_path no existe.
        ValueError: Si el JSON es inválido o no contiene mapas.
    """
    plan = load_cartography_plan(plan_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[SchematicMapResult] = []
    for map_dict in plan["maps"]:
        filename = map_dict.get("output_filename", f"{map_dict.get('map_id', 'MAP')}.png")
        out_path = out_dir / filename
        result = generate_schematic_map(map_dict, out_path, config)
        results.append(result)

    return results


# ---------------------------------------------------------------------------
# build_map_generation_report
# ---------------------------------------------------------------------------

def build_map_generation_report(results: list[SchematicMapResult]) -> str:
    """Genera markdown con el resumen de mapas esquemáticos generados."""
    generated = [r for r in results if r.status == "GENERATED_PROVISIONAL"]
    errors = [r for r in results if r.status == "ERROR"]

    lines = [
        "# Informe de generación de mapas esquemáticos — CA-11",
        "",
        "> **AVISO**: Los mapas generados son esquemáticos provisionales en modo test. "
        "No son aptos para presentación administrativa ni sustituyen cartografía oficial.",
        "",
        f"- **Mapas planificados**: {len(results)}",
        f"- **Generados (PROVISIONAL)**: {len(generated)}",
        f"- **Con error**: {len(errors)}",
        "",
        "## Resultados",
        "",
        "| ID | Título | Archivo | Estado |",
        "|----|--------|---------|--------|",
    ]
    for r in results:
        fname = Path(r.output_path).name
        lines.append(
            f"| {r.map_id} | {r.title} | `{fname}` | {r.status} |"
        )

    if errors:
        lines += ["", "## Errores", ""]
        for r in errors:
            lines.append(f"- **{r.map_id}**: {'; '.join(r.warnings)}")

    lines += [
        "",
        "---",
        "",
        "*Generado por CA-11 — Generador de mapas esquemáticos offline.*  ",
        "*Para cartografía oficial usar módulos con WMS/WMTS reales.*",
    ]
    return "\n".join(lines)
