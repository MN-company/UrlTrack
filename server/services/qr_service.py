"""
QR code generation service.
Uses segno for QR encoding and Pillow for gradients, dot styles, and logo compositing.
"""

import io
import json
import math
import re
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

try:
    import segno
except ImportError:  # pragma: no cover - requirements include segno
    segno = None


DEFAULT_CONFIG = {
    "fg_color": "#000000",
    "bg_color": "#ffffff",
    "gradient_color": None,
    "gradient_direction": "diagonal",
    "error_correction": "M",
    "dot_style": "square",
    "logo_path": None,
    "transparent_bg": False,
}

ERROR_LEVELS = {"L", "M", "Q", "H"}
GRADIENT_DIRECTIONS = {"horizontal", "vertical", "diagonal", "radial"}
DOT_STYLES = {"square", "rounded", "circle"}
LOGO_MIN_EC = "H"
HEX_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _normalize_hex(value: object, default: str) -> str:
    if not isinstance(value, str) or not HEX_RE.match(value.strip()):
        return default
    value = value.strip()
    if not value.startswith("#"):
        value = f"#{value}"
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value.upper()


def parse_config(qr_config_json: Optional[str]) -> dict:
    """Parse and validate qr_config JSON, filling defaults for missing keys."""
    cfg = dict(DEFAULT_CONFIG)
    if qr_config_json:
        try:
            override = json.loads(qr_config_json)
        except (json.JSONDecodeError, TypeError):
            override = {}
        if isinstance(override, dict):
            for key in DEFAULT_CONFIG:
                if key in override and override[key] is not None:
                    cfg[key] = override[key]

    cfg["fg_color"] = _normalize_hex(cfg.get("fg_color"), DEFAULT_CONFIG["fg_color"])
    cfg["bg_color"] = _normalize_hex(cfg.get("bg_color"), DEFAULT_CONFIG["bg_color"])
    cfg["gradient_color"] = (
        _normalize_hex(cfg.get("gradient_color"), DEFAULT_CONFIG["fg_color"])
        if cfg.get("gradient_color")
        else None
    )
    cfg["gradient_direction"] = (
        str(cfg.get("gradient_direction"))
        if str(cfg.get("gradient_direction")) in GRADIENT_DIRECTIONS
        else DEFAULT_CONFIG["gradient_direction"]
    )
    cfg["error_correction"] = (
        str(cfg.get("error_correction", "M")).upper()
        if str(cfg.get("error_correction", "M")).upper() in ERROR_LEVELS
        else DEFAULT_CONFIG["error_correction"]
    )
    cfg["dot_style"] = (
        str(cfg.get("dot_style"))
        if str(cfg.get("dot_style")) in DOT_STYLES
        else DEFAULT_CONFIG["dot_style"]
    )
    cfg["transparent_bg"] = bool(cfg.get("transparent_bg"))
    cfg["logo_path"] = str(cfg.get("logo_path")) if cfg.get("logo_path") else None
    return cfg


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = _normalize_hex(hex_color, "#000000").lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _gradient_color_at(x: int, y: int, w: int, h: int, c1: tuple[int, int, int], c2: tuple[int, int, int], direction: str):
    if direction == "horizontal":
        t = x / max(w - 1, 1)
    elif direction == "vertical":
        t = y / max(h - 1, 1)
    elif direction == "radial":
        cx, cy = w / 2, h / 2
        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        t = min(dist / max(math.sqrt(cx**2 + cy**2), 1), 1.0)
    else:
        t = (x / max(w - 1, 1) + y / max(h - 1, 1)) / 2
    return tuple(int(c1[idx] + (c2[idx] - c1[idx]) * t) for idx in range(3))


def _render_matrix(qr, config: dict, scale: int) -> Image.Image:
    matrix = tuple(qr.matrix)
    module_count = len(matrix)
    border = int(getattr(qr, "default_border_size", 4) or 4)
    size = (module_count + border * 2) * scale
    bg = (255, 255, 255, 0) if config.get("transparent_bg") else (*_hex_to_rgb(config["bg_color"]), 255)
    img = Image.new("RGBA", (size, size), bg)
    draw = ImageDraw.Draw(img)
    c1 = _hex_to_rgb(config["fg_color"])
    c2 = _hex_to_rgb(config["gradient_color"] or config["fg_color"])
    direction = config.get("gradient_direction", "diagonal")
    dot_style = config.get("dot_style", "square")
    radius = max(1, int(scale * 0.36))

    for row_idx, row in enumerate(matrix):
        for col_idx, module in enumerate(row):
            if not module:
                continue
            x0 = (col_idx + border) * scale
            y0 = (row_idx + border) * scale
            x1 = x0 + scale
            y1 = y0 + scale
            color = (*_gradient_color_at(x0, y0, size, size, c1, c2, direction), 255)
            if dot_style == "circle":
                inset = max(1, scale // 8)
                draw.ellipse((x0 + inset, y0 + inset, x1 - inset, y1 - inset), fill=color)
            elif dot_style == "rounded":
                draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=color)
            else:
                draw.rectangle((x0, y0, x1, y1), fill=color)
    return img


def _apply_logo(img: Image.Image, logo_path: str) -> Image.Image:
    try:
        logo = Image.open(logo_path).convert("RGBA")
    except Exception:
        return img

    qr_w, qr_h = img.size
    max_logo = int(qr_w * 0.25)
    lw, lh = logo.size
    if not lw or not lh:
        return img
    scale = min(max_logo / lw, max_logo / lh)
    logo = logo.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.LANCZOS)

    pad = max(6, qr_w // 64)
    bg = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), (255, 255, 255, 255))
    mask = Image.new("L", bg.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bg.width - 1, bg.height - 1), radius=pad * 2, fill=255)
    padded = Image.new("RGBA", bg.size, (255, 255, 255, 0))
    padded.paste(bg, (0, 0), mask)
    padded.paste(logo, (pad, pad), logo)

    result = img.copy().convert("RGBA")
    pos = ((qr_w - padded.width) // 2, (qr_h - padded.height) // 2)
    result.paste(padded, pos, padded)
    return result


def _effective_error_correction(config: dict) -> str:
    return LOGO_MIN_EC if config.get("logo_path") else config.get("error_correction", "M")


def generate_qr_png(url: str, config: dict, scale: int = 10) -> bytes:
    """Generate QR code as PNG bytes."""
    if segno is None:
        raise RuntimeError("segno is required to generate QR codes")
    config = parse_config(json.dumps(config))
    ec = _effective_error_correction(config)
    qr = segno.make_qr(url, error=ec.lower())
    img = _render_matrix(qr, config, max(1, min(int(scale), 20)))
    logo_path = config.get("logo_path")
    if logo_path and Path(logo_path).exists():
        img = _apply_logo(img, logo_path)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def generate_qr_svg(url: str, config: dict, scale: int = 10) -> str:
    """Generate QR code as SVG string. Gradients, dot styles, and logos are PNG-only."""
    if segno is None:
        raise RuntimeError("segno is required to generate QR codes")
    config = parse_config(json.dumps(config))
    ec = _effective_error_correction(config)
    qr = segno.make_qr(url, error=ec.lower())
    buffer = io.BytesIO()
    qr.save(
        buffer,
        kind="svg",
        scale=max(1, min(int(scale), 20)),
        dark=config["fg_color"],
        light=None if config.get("transparent_bg") else config["bg_color"],
    )
    return buffer.getvalue().decode("utf-8")
