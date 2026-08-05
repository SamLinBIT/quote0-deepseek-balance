"""Local PNG export of the combined dashboard (no push to device).

Renders the dashboard at the physical e-ink resolution (296x152) with a
baked-in 5x7 bitmap font — pure standard library, matching the project's
zero dependency rule. Mirrors the Canvas layout from ``dashboard.py``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from deepseek_balance.layout import _format_balance
from deepseek_balance.heatmap import (
    _cell_pattern,
    _make_grayscale_png,
    _render_4col_grid_pixels,
    render_28day_heatmap,
)

# ---------------------------------------------------------------------------
# Canvas (physical e-ink resolution)
# ---------------------------------------------------------------------------
W = 296
H = 152
WHITE = 255
BLACK = 0
DIM = 128  # dimmed icon for error state

# Layout constants
PAD = 8
LEFT_W = 70
COL_GAP = 12
RIGHT_X = PAD + LEFT_W + COL_GAP  # 90
LABEL_COL_W = 18  # day-label column
GAP_X = 3
GAP_Y = 3
CELL_W = 42
CELL_H = 12
GRID_X = RIGHT_X + LABEL_COL_W + GAP_X  # 111
GRID_W = 4 * CELL_W + 3 * GAP_X  # 177

# ---------------------------------------------------------------------------
# 5x7 bitmap font (rows of 5 bits, '1' = black)
# ---------------------------------------------------------------------------
_FONT: dict[str, tuple[str, ...]] = {
    " ": ("00000",) * 7,
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "b": ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    "c": ("00000", "00000", "01110", "10000", "10000", "10000", "01110"),
    "d": ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    "f": ("00110", "01001", "01000", "11100", "01000", "01000", "01000"),
    "g": ("00000", "01111", "10001", "10001", "01111", "00001", "01110"),
    "h": ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    "i": ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    "j": ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    "k": ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "m": ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    "n": ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    "o": ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    "p": ("00000", "11110", "10001", "10001", "11110", "10000", "10000"),
    "q": ("00000", "01111", "10001", "10001", "01111", "00001", "00001"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "s": ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    "t": ("01000", "01000", "11100", "01000", "01000", "01001", "00110"),
    "u": ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    "v": ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    "w": ("00000", "00000", "10001", "10001", "10101", "10101", "01010"),
    "x": ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    "y": ("00000", "00000", "10001", "10001", "10001", "01111", "00001"),
    "z": ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "01100", "00100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "/": ("00001", "00010", "00010", "00100", "00100", "01000", "10000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "¥": ("11111", "00100", "00100", "01000", "00100", "01000", "01000"),
    "✓": ("10000", "01000", "00100", "00010", "00001", "01110", "00000"),
    "✗": ("00000", "10001", "01010", "00100", "01010", "10001", "00000"),
    "今": ("00100", "01010", "01010", "11111", "00100", "00100", "01000"),
    "日": ("11111", "10001", "10001", "11111", "10001", "10001", "11111"),
}


def _fill(canvas: list[list[int]], x: int, y: int, w: int, h: int, val: int = BLACK) -> None:
    """Fill a rectangle, clipped to the canvas bounds."""
    x0, x1 = max(x, 0), min(x + w, W)
    y0, y1 = max(y, 0), min(y + h, H)
    for yy in range(y0, y1):
        row = canvas[yy]
        for xx in range(x0, x1):
            row[xx] = val


def _text_width(text: str, scale: int, spacing: int = 1) -> int:
    """Width of text at the given scale (excludes trailing advance)."""
    n = sum(1 for ch in text if ch in _FONT)
    if n == 0:
        return 0
    return (n * (5 + spacing) - spacing) * scale


def _draw_text(
    canvas: list[list[int]],
    x: int,
    y: int,
    text: str,
    scale: int = 2,
    spacing: int = 1,
) -> int:
    """Draw text at (x, y) and return the advance position."""
    px = x
    adv = (5 + spacing) * scale
    for ch in text:
        glyph = _FONT.get(ch)
        if glyph is None:
            px += adv
            continue
        for r, row in enumerate(glyph):
            for c, bit in enumerate(row):
                if bit == "1":
                    _fill(canvas, px + c * scale, y + r * scale, scale, scale)
        px += adv
    return px


def _draw_text_centered(
    canvas: list[list[int]], cx: int, y: int, text: str, scale: int = 2, spacing: int = 1
) -> None:
    _draw_text(canvas, cx - _text_width(text, scale, spacing) // 2, y, text, scale, spacing)


def _draw_text_wrapped(
    canvas: list[list[int]],
    x: int,
    y: int,
    text: str,
    scale: int,
    max_width: int,
) -> None:
    """Word-wrap text into lines no wider than max_width."""
    lines: list[str] = []
    for word in text.split():
        if lines and _text_width(f"{lines[-1]} {word}", scale) <= max_width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    line_h = 7 * scale
    for i, line in enumerate(lines):
        _draw_text(canvas, x, y + i * line_h, line, scale)


def _draw_icon(canvas: list[list[int]], cx: int, cy: int, r: int, val: int = BLACK) -> None:
    """Draw a ring icon (placeholder for the DeepSeek favicon) plus 'DS'."""
    ring_inner = r - 3
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d2 = dx * dx + dy * dy
            if ring_inner * ring_inner <= d2 <= r * r:
                _fill(canvas, cx + dx, cy + dy, 1, 1, val)
    _draw_text_centered(canvas, cx, cy - 7, "DS", 2)


def _draw_swatch(canvas: list[list[int]], x: int, y: int, level: int, size: int = 12) -> None:
    """Draw a legend swatch using the same baked-in cell pattern."""
    border = 1
    for yy in range(size):
        for xx in range(size):
            if xx < border or xx >= size - border or yy < border or yy >= size - border:
                canvas[y + yy][x + xx] = BLACK
            elif _cell_pattern(xx - border, yy - border, level) == BLACK:
                canvas[y + yy][x + xx] = BLACK


def _paste(
    canvas: list[list[int]], pixels: list[list[int]], x0: int, y0: int
) -> None:
    """Blit a black/white pixel array onto the canvas at 1:1."""
    for y, row in enumerate(pixels):
        for x, v in enumerate(row):
            if v == BLACK:
                _fill(canvas, x0 + x, y0 + y, 1, 1)


def render_dashboard_png(
    *,
    balance_display: str,
    currency: str,
    status_text: str,
    error_message: str | None = None,
    timestamp: str = "",
    costs: dict[str, Decimal] | None = None,
) -> bytes:
    """Render the combined dashboard as a 296x152 grayscale PNG.

    Returns PNG bytes ready to be written to disk.
    """
    hm = render_28day_heatmap(costs, currency)
    grid_pixels = _render_4col_grid_pixels(hm["grid"])

    canvas: list[list[int]] = [[WHITE for _ in range(W)] for _ in range(H)]

    # ---- Left column (70 px) ----
    left_cx = PAD + LEFT_W // 2  # 43
    icon_gray = DIM if error_message else BLACK
    _draw_icon(canvas, left_cx, 56, 22, icon_gray)
    _draw_text_centered(canvas, left_cx, 82, status_text, 1)
    _draw_text_centered(canvas, left_cx, 92, timestamp, 1)
    _draw_text_centered(canvas, left_cx, 103, balance_display, 2, spacing=0)

    if error_message:
        _draw_text_wrapped(canvas, PAD, 121, error_message, 1, LEFT_W)

    # ---- Right column: header dates ----
    grid_y = 22
    for col, label in enumerate(hm["col_dates"]):
        cell_cx = GRID_X + col * (CELL_W + GAP_X) + CELL_W // 2
        _draw_text_centered(canvas, cell_cx, 13, label, 1)

    # ---- Right column: day labels + grid ----
    for row, label in enumerate(hm["day_labels"]):
        ly = grid_y + row * (CELL_H + GAP_Y) + (CELL_H - 7) // 2
        _draw_text_centered(canvas, RIGHT_X + LABEL_COL_W // 2, ly, label, 1)
    _paste(canvas, grid_pixels, GRID_X, grid_y)

    # ---- Right column: legend (swatches + today's cost) ----
    today_str = _format_balance(
        costs.get(date.today().isoformat(), Decimal("0")) if costs else Decimal("0"),
        currency,
    )
    lx = GRID_X
    for level in range(5):
        _draw_swatch(canvas, lx, 126, level)
        lx += 12 + GAP_X
    legend_text = f"今日 {today_str}"
    _draw_text(canvas, W - PAD - _text_width(legend_text, 1), 128, legend_text, 1)

    return _make_grayscale_png(W, H, canvas)
