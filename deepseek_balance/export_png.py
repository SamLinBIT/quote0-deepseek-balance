"""Local PNG export of the combined dashboard (no push to device).

Renders the dashboard on an internal 4x canvas (1184x608), then downsamples
4:1 to the physical e-ink resolution (296x152) with an Otsu threshold —
antialiased text edges without external dependencies. Mirrors the Canvas
layout from ``dashboard.py``.

Output is a strict 1-bit black/white PNG (bit depth 1, grayscale) —
identical to how the e-ink device renders ``img-levels-2`` content.
"""

from __future__ import annotations

import re
import ssl
import struct
import urllib.request
import zlib
from datetime import date
from decimal import Decimal
from typing import Any

from deepseek_balance.layout import _format_balance
from deepseek_balance.heatmap import (
    _cell_pattern,
    _render_4col_grid_pixels,
    render_28day_heatmap,
)

# ---------------------------------------------------------------------------
# Canvas — internal 4x supersampled, output at physical resolution
# ---------------------------------------------------------------------------
SCALE = 4
OUT_W = 296
OUT_H = 152
W = OUT_W * SCALE  # 1184
H = OUT_H * SCALE  # 608
WHITE = 255
BLACK = 0

# Layout constants (physical px, used ×SCALE internally)
PAD = 8 * SCALE
LEFT_W = 70 * SCALE
COL_GAP = 12 * SCALE
RIGHT_X = PAD + LEFT_W + COL_GAP  # 360
LABEL_COL_W = 18 * SCALE  # day-label column
GAP_X = 3 * SCALE
GAP_Y = 3 * SCALE
CELL_W = 42 * SCALE
CELL_H = 12 * SCALE
GRID_X = RIGHT_X + LABEL_COL_W + GAP_X  # 444
GRID_W = 4 * CELL_W + 3 * GAP_X  # 708
TEXT_H = 7 * SCALE  # glyph height at scale 1

ICON_URL = "https://cdn.deepseek.com/platform/favicon.png"
ICON_SIZE = 50 * SCALE

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
    "¥": ("11111", "00100", "00100", "11111", "00100", "01000", "00010"),
    "✓": ("10000", "01000", "00100", "00010", "00001", "01110", "00000"),
    "✗": ("00000", "10001", "01010", "00100", "01010", "10001", "00000"),
    "今": ("00100", "01010", "01010", "11111", "00100", "00100", "01000"),
    "日": ("11111", "10001", "10001", "11111", "10001", "10001", "11111"),
    "元": ("11111", "00100", "00100", "11111", "00100", "01010", "00100"),
}


# ---------------------------------------------------------------------------
# 1-bit PNG encoder (bit depth 1, grayscale, no palette)
# ---------------------------------------------------------------------------


def _make_1bit_png(width: int, height: int, pixels: list[list[int]]) -> bytes:
    """Encode a binary pixel array as a 1-bit grayscale PNG.

    ``pixels[y][x]`` is 0 (black) or 255 (white). Pixels are packed MSB-first,
    8 per byte, with a None filter byte on every scanline.
    """
    row_bytes = (width + 7) // 8
    raw = bytearray()
    for y in range(height):
        raw.append(0x00)  # filter: none
        for bx in range(row_bytes):
            byte = 0
            base = bx * 8
            for i in range(8):
                x = base + i
                if x < width and pixels[y][x] >= 128:  # 1-bit grayscale: 1 = white
                    byte |= 0x80 >> i
            raw.append(byte)

    compressed = zlib.compress(bytes(raw))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)
    return (
        sig
        + _png_chunk(b"IHDR", ihdr_data)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build one PNG chunk (length + type + data + CRC)."""
    c = chunk_type + data
    crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + c + crc


# ---------------------------------------------------------------------------
# DeepSeek favicon (real icon, downloaded at render time)
# ---------------------------------------------------------------------------


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _decode_png_rgba(data: bytes) -> tuple[int, int, list[list[tuple[int, int, int, int]]]]:
    """Decode a PNG to an RGBA pixel array.

    Supports 8-bit color types 2 (RGB), 3 (palette), 6 (RGBA) and
    0 (grayscale), no interlace.
    """
    pos = 8
    idat = b""
    width = height = bit_depth = color_type = None
    palette: list[tuple[int, int, int]] = []
    trns: dict[int, int] = {}

    while pos < len(data):
        ln = struct.unpack(">I", data[pos : pos + 4])[0]
        ctype = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + ln]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif ctype == b"PLTE":
            palette = [
                (chunk[i], chunk[i + 1], chunk[i + 2]) for i in range(0, len(chunk), 3)
            ]
        elif ctype == b"tRNS":
            trns = dict(enumerate(chunk))
        elif ctype == b"IDAT":
            idat += chunk
        pos += 12 + ln

    if bit_depth != 8 or color_type not in (0, 2, 3, 6):
        raise ValueError(f"Unsupported PNG format: bit depth {bit_depth}, type {color_type}")

    bpp = {0: 1, 2: 3, 3: 1, 6: 4}[color_type]
    raw = zlib.decompress(idat)
    stride = width * bpp + 1

    rows: list[list[int]] = []
    prev = bytearray(width * bpp)
    for y in range(height):
        row = bytearray(raw[y * stride + 1 : (y + 1) * stride])
        f = raw[y * stride]
        if f == 1:
            for i in range(bpp, len(row)):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif f == 2:
            for i in range(len(row)):
                row[i] = (row[i] + prev[i]) & 255
        elif f == 3:
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 255
        prev = row
        rows.append(row)

    rgba: list[list[tuple[int, int, int, int]]] = []
    for row in rows:
        line: list[tuple[int, int, int, int]] = []
        for i in range(width):
            if color_type == 3:
                r, g, b = palette[row[i]]
                a = trns.get(row[i], 255)
            elif color_type == 6:
                j = i * 4
                r, g, b, a = row[j], row[j + 1], row[j + 2], row[j + 3]
            elif color_type == 2:
                j = i * 3
                r, g, b, a = row[j], row[j + 1], row[j + 2], 255
            else:
                r = g = b = row[i]
                a = 255
            line.append((r, g, b, a))
        rgba.append(line)
    return width, height, rgba


def _fetch_favicon_pixels(size: int = ICON_SIZE) -> list[list[int]] | None:
    """Download the DeepSeek favicon, composite on white, threshold to binary.

    Returns a ``size x size`` pixel array (0 = black, 255 = white),
    or None if the icon cannot be fetched/decoded.
    """
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(ICON_URL, timeout=10, context=ctx) as resp:
            data = resp.read()
        src_w, src_h, rgba = _decode_png_rgba(data)
    except Exception:
        return None

    out: list[list[int]] = []
    for y in range(size):
        sy = min(y * src_h // size, src_h - 1)
        row: list[int] = []
        for x in range(size):
            sx = min(x * src_w // size, src_w - 1)
            r, g, b, a = rgba[sy][sx]
            if a < 128:
                row.append(WHITE)
                continue
            r = r * a // 255 + 255 * (255 - a) // 255
            g = g * a // 255 + 255 * (255 - a) // 255
            b = b * a // 255 + 255 * (255 - a) // 255
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            row.append(BLACK if gray < 128 else WHITE)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------


def _strip_cny(display: str) -> str:
    """Strip the leading ¥ symbol, keep the digits only."""
    return re.sub(r"^¥", "", display)


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
    center: bool = False,
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
        if center:
            _draw_text_centered(canvas, x + max_width // 2, y + i * line_h, line, scale)
        else:
            _draw_text(canvas, x, y + i * line_h, line, scale)


def _draw_ring_icon(canvas: list[list[int]], cx: int, cy: int, r: int) -> None:
    """Fallback ring icon (used only if the favicon cannot be fetched)."""
    ring_inner = r - 3
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d2 = dx * dx + dy * dy
            if ring_inner * ring_inner <= d2 <= r * r:
                _fill(canvas, cx + dx, cy + dy, 1, 1)
    _draw_text_centered(canvas, cx, cy - 7, "DS", 2)


def _draw_swatch(canvas: list[list[int]], x: int, y: int, level: int, size: int = 12 * SCALE) -> None:
    """Draw a legend swatch using the same baked-in cell pattern."""
    border = 1 * SCALE
    for yy in range(size):
        for xx in range(size):
            if xx < border or xx >= size - border or yy < border or yy >= size - border:
                canvas[y + yy][x + xx] = BLACK
            elif _cell_pattern((xx - border) // SCALE, (yy - border) // SCALE, level) == BLACK:
                canvas[y + yy][x + xx] = BLACK


def _paste(
    canvas: list[list[int]], pixels: list[list[int]], x0: int, y0: int
) -> None:
    """Blit a black/white pixel array onto the canvas at SCALEx."""
    for y, row in enumerate(pixels):
        for x, v in enumerate(row):
            if v == BLACK:
                _fill(canvas, x0 + x * SCALE, y0 + y * SCALE, SCALE, SCALE)


# ---------------------------------------------------------------------------
# Downsampling: local threshold on 4x4 blocks, small text drawn 1:1
# ---------------------------------------------------------------------------


def _compose_binary(big: list[list[int]], small: list[list[int]]) -> list[list[int]]:
    """Blend the 4x canvas (large glyphs, icons, patterns) with the 1x canvas
    (small text drawn directly at physical resolution).

    A 4x4 block becomes black when ≥25% of its pixels are black — preserves
    the baked-in heatmap patterns (17-100% density) and 2px+ strokes.
    """
    out: list[list[int]] = [[small[y][x] for x in range(OUT_W)] for y in range(OUT_H)]
    for y in range(OUT_H):
        row = out[y]
        for x in range(OUT_W):
            if row[x] == BLACK:
                continue
            black = 0
            for dy in range(SCALE):
                src = big[y * SCALE + dy]
                for dx in range(SCALE):
                    if src[x * SCALE + dx] == BLACK:
                        black += 1
            if black * 100 >= 25 * SCALE * SCALE:
                row[x] = BLACK
    return out


def render_dashboard_png(
    *,
    balance_display: str,
    currency: str,
    status_text: str,
    error_message: str | None = None,
    timestamp: str = "",
    costs: dict[str, Decimal] | None = None,
) -> bytes:
    """Render the combined dashboard as a 296x152 1-bit grayscale PNG.

    Large glyphs, icons, and heatmap patterns are rendered on a 4x canvas and
    downsampled with a local threshold; small text is drawn 1:1 at physical
    resolution to keep 7px-tall glyphs crisp.
    """
    hm = render_28day_heatmap(costs, currency)
    grid_pixels = _render_4col_grid_pixels(hm["grid"])
    favicon = _fetch_favicon_pixels()

    big: list[list[int]] = [[WHITE for _ in range(W)] for _ in range(H)]
    small: list[list[int]] = [[WHITE for _ in range(OUT_W)] for _ in range(OUT_H)]

    # ---- Left column (70 px) ----
    # Vertical spacing: normal layout spreads items across the full height;
    # error state drops the balance line and fits the 3-line message instead.
    left_cx = PAD + LEFT_W // 2  # 172
    if error_message:
        icon_y, sy, tsy, ey = 14, 76, 90, 106
    else:
        icon_y, sy, tsy, by = 20, 84, 101, 118
    if favicon is not None:
        for y in range(ICON_SIZE):
            for x in range(ICON_SIZE):
                if favicon[y][x] == BLACK:
                    _fill(big, left_cx - ICON_SIZE // 2 + x, icon_y * SCALE + y, 1, 1)
    else:
        _draw_ring_icon(big, left_cx, icon_y * SCALE + ICON_SIZE // 2, ICON_SIZE // 2 - 3 * SCALE)
    _draw_text_centered(small, left_cx // SCALE, sy, status_text, 1)
    _draw_text_centered(small, left_cx // SCALE, tsy, timestamp, 1)

    if error_message:
        _draw_text_wrapped(
            small, PAD // SCALE, ey, error_message, 1, LEFT_W // SCALE, center=True
        )
    else:
        balance_display = _strip_cny(balance_display)
        _draw_text_centered(big, left_cx, by * SCALE, balance_display, 2 * SCALE, spacing=0)

    # ---- Right column: header dates ----
    grid_y = 22 * SCALE
    for col, label in enumerate(hm["col_dates"]):
        cell_cx = GRID_X + col * (CELL_W + GAP_X) + CELL_W // 2
        _draw_text_centered(small, cell_cx // SCALE, 13, label, 1)

    # ---- Right column: day labels + grid ----
    for row, label in enumerate(hm["day_labels"]):
        ly = 22 + row * ((CELL_H + GAP_Y) // SCALE) + ((CELL_H - TEXT_H) // SCALE) // 2
        _draw_text_centered(small, (RIGHT_X + LABEL_COL_W // 2) // SCALE, ly, label, 1)
    _paste(big, grid_pixels, GRID_X, grid_y)

    # ---- Right column: legend (swatches + today's cost) ----
    today_str = _format_balance(
        costs.get(date.today().isoformat(), Decimal("0")) if costs else Decimal("0"),
        currency,
    )
    lx = GRID_X
    legend_y = 126 * SCALE
    for level in range(5):
        _draw_swatch(big, lx, legend_y, level)
        lx += 12 * SCALE + GAP_X
    legend_text = f"今日 {_strip_cny(today_str)}"
    _draw_text(
        small,
        OUT_W - PAD // SCALE - _text_width(legend_text, 1),
        128,
        legend_text,
        1,
    )

    binary = _compose_binary(big, small)
    return _make_1bit_png(OUT_W, OUT_H, binary)
