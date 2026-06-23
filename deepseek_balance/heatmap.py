"""30-day spending heatmap — PNG generation + Canvas payload builder.

Uses pure-Python PNG generation (struct + zlib, zero dependencies) to create
grayscale heatmap images that are embedded as base64 data URIs in img elements.
The Canvas API's img-dither-diffusion + img-levels-8 classes produce the actual
grayscale rendering on the e-ink display.
"""

from __future__ import annotations

import base64
import struct
import zlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from deepseek_balance.usage_data import load_usage, get_daily_cost
from deepseek_balance.history import load_history
from deepseek_balance.layout import _format_balance

# ---------------------------------------------------------------------------
# Grid geometry (pixels)
# ---------------------------------------------------------------------------
CELL_W = 36
CELL_H = 13
GAP_X = 2
GAP_Y = 1
BORDER = 1  # px border on each cell

COLS = 7
ROWS = 7  # Monday (top) to Sunday (bottom)

GRID_W = COLS * CELL_W + (COLS - 1) * GAP_X  # 7×36 + 6×2 = 264
GRID_H = ROWS * CELL_H + (ROWS - 1) * GAP_Y  # 7×13 + 6×1 = 97

# ---------------------------------------------------------------------------
# Baked-in binary patterns per heat level (0=black, 255=white)
# ---------------------------------------------------------------------------
# Because the e-ink display and Canvas API server do NOT reliably produce
# distinguishable grayscale on small div/img elements, we pre-render each
# cell with a distinct black-and-white pattern.  Patterns are chosen to be
# visually distinguishable at 36×13 px cell size.
#
# Level 0 = no spending (hollow), 1 = 5-dot plus (~17%),
# 2 = horizontal stripes (~33%), 3 = checkerboard (50%), 4 = solid black.


def _cell_pattern(x: int, y: int, level: int) -> int:
    """Return 0 (black) or 255 (white) for a cell-interior pixel at (x,y).

    x, y are relative to the cell's top-left interior (0 ≤ x < CELL_W, 0 ≤ y < CELL_H).
    """
    if level == 0:
        return 255  # all white — "no spending today"
    elif level == 1:
        # 5-dot plus (+) pattern — light, structured texture (~17% density)
        tx, ty = x % 6, y % 5
        # plus centered at (2,2): center + 4 orthogonal arms
        return 0 if (tx, ty) in ((2, 1), (1, 2), (2, 2), (3, 2), (2, 3)) else 255
    elif level == 2:
        # Horizontal stripe every 3rd row — medium texture
        return 0 if (y % 3 == 0) else 255
    elif level == 3:
        # 2×2 checkerboard — dense texture
        return 0 if ((x // 2) + (y // 2)) % 2 == 0 else 255
    elif level == 4:
        return 0  # solid black — "peak spending"
    return 255


def _cell_border_color(level: int) -> int:
    """Border color for a cell (0=black, 255=white)."""
    return 0  # all borders are black on white background


BORDER_PX = 1  # cell border width

# ---------------------------------------------------------------------------
# Minimal PNG encoder (grayscale, 8-bit, no palette)
# ---------------------------------------------------------------------------


def _make_grayscale_png(width: int, height: int, pixels: list[list[int]]) -> bytes:
    """Encode a 2-D greyscale pixel array as a PNG byte string.

    ``pixels[y][x]`` is an integer in 0…255 (0 = black, 255 = white).
    """
    # Build raw scanlines: filter byte (0x00 = None) + width bytes
    raw = bytearray()
    for y in range(height):
        raw.append(0x00)  # filter: none
        raw.extend(pixels[y])

    compressed = zlib.compress(bytes(raw))

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
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


def _png_to_data_uri(png_bytes: bytes) -> str:
    """Convert raw PNG bytes to a ``data:image/png;base64,…`` string."""
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# Heatmap grid → PNG
# ---------------------------------------------------------------------------


def _render_grid_png(
    grid: list[list[int | None]],  # [row][col]  heat level 0-4 or None
) -> bytes:
    """Render the 7×6 heatmap grid as a binary PNG with baked-in patterns.

    Each cell is filled with a distinct black/white pattern by level.
    Returns PNG bytes ready for ``_png_to_data_uri``.
    """
    pixels = [[255 for _ in range(GRID_W)] for _ in range(GRID_H)]

    for row in range(ROWS):
        for col in range(COLS):
            level = grid[row][col]
            x0 = col * (CELL_W + GAP_X)
            y0 = row * (CELL_H + GAP_Y)

            # If no data at all, leave the cell white (gap color) — invisible grid
            if level is None:
                continue

            for dy in range(CELL_H):
                for dx in range(CELL_W):
                    px, py = x0 + dx, y0 + dy
                    if not (0 <= px < GRID_W and 0 <= py < GRID_H):
                        continue

                    # Border
                    if dx < BORDER_PX or dx >= CELL_W - BORDER_PX or dy < BORDER_PX or dy >= CELL_H - BORDER_PX:
                        pixels[py][px] = 0  # black border
                    else:
                        # Interior pattern
                        ix = dx - BORDER_PX
                        iy = dy - BORDER_PX
                        iw = CELL_W - 2 * BORDER_PX
                        ih = CELL_H - 2 * BORDER_PX
                        if iw > 0 and ih > 0:
                            pixels[py][px] = _cell_pattern(ix, iy, level)

    return _make_grayscale_png(GRID_W, GRID_H, pixels)


def _render_swatch_png(level: int, size: int = 12) -> bytes:
    """Render a small square swatch for the legend using the same pattern."""
    border = 1
    pixels = [[255 for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            if x < border or x >= size - border or y < border or y >= size - border:
                pixels[y][x] = _cell_border_color(level)
            else:
                pixels[y][x] = _cell_pattern(x - border, y - border, level)
    return _make_grayscale_png(size, size, pixels)


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------


def gather_30day_costs() -> dict[str, Decimal]:
    """Collect daily DeepSeek costs for the last 30 days.

    Prefers imported CSV costs, falls back to balance-history deltas.
    Returns ``{date_str: Decimal}`` — missing entries mean no data.
    """
    usage = load_usage()
    history = load_history()

    # Index snapshots by date for O(1) lookup
    snapshots: dict[str, Decimal] = {}
    for snap in history.snapshots:
        if snap.total_balance:
            snapshots[snap.date] = Decimal(snap.total_balance)

    today = date.today()
    costs: dict[str, Decimal] = {}

    for i in range(30):
        d = today - timedelta(days=29 - i)
        d_str = d.isoformat()

        # 1) Prefer imported CSV data
        csv_cost = get_daily_cost(usage, d_str)
        if csv_cost is not None and csv_cost >= 0:
            costs[d_str] = csv_cost
            continue

        # 2) Fall back to balance delta (yesterday - today)
        #    Need snapshots for BOTH d-1 and d
        prev_str = (d - timedelta(days=1)).isoformat()
        prev_balance = snapshots.get(prev_str)
        curr_balance = snapshots.get(d_str)
        if prev_balance is not None and curr_balance is not None:
            delta = prev_balance - curr_balance
            if delta >= 0:
                costs[d_str] = delta
            # else: balance went up (refund?), don't record negative cost

    return costs


def _compute_level_thresholds(positive_costs: list[Decimal]) -> tuple[float, float, float]:
    """Return (t1, t2, t3) boundaries for levels 1/2, 2/3, 3/4.

    Uses quartile-based thresholds (P25, P50, P75) when ≥10 data points are
    available, ensuring roughly equal distribution across heat levels.
    Falls back to fixed-ratio thresholds (25%, 50%, 75% of max) for small samples.
    """
    sorted_costs = sorted(float(c) for c in positive_costs)
    n = len(sorted_costs)

    if n < 10:
        # Fallback: fixed ratios of max (preserves current behavior)
        max_val = sorted_costs[-1] if n > 0 else 0.0
        return (max_val * 0.25, max_val * 0.50, max_val * 0.75)

    # Linear interpolation percentile (no numpy needed)
    def _percentile(p: float) -> float:
        k = (n - 1) * p / 100.0
        f = int(k)
        c = k - f
        if f + 1 < n:
            return sorted_costs[f] + c * (sorted_costs[f + 1] - sorted_costs[f])
        return sorted_costs[f]

    return (_percentile(25), _percentile(50), _percentile(75))


def _assign_heat_levels(
    costs: dict[str, Decimal],
) -> tuple[list[list[int | None]], list[list[Decimal | None]], list[str], list[int], int, int | None, int | None]:
    """Map daily costs to heat levels (0-4) in a 7-row × 6-col grid.

    Returns:
        grid:       7×6 heat levels (0-4 or None)
        values:     7×6 Decimal costs (for tooltip / avg calc)
        day_labels: per-row labels ["一","二",…,"日"]
        col_dates:  list of 6 date strings for the first day in each column
        today_col, today_row: position of today's cell (or None)
    """
    today = date.today()
    start = today - timedelta(days=29)

    # Build the 30-day linear array, aligned to Monday
    # Find the Monday on or before `start`
    monday_offset = start.weekday()  # 0=Mon
    window_start = start - timedelta(days=monday_offset)  # Monday of start week
    # How many columns needed to cover start..today?
    window_end = today
    days_in_window = (window_end - window_start).days + 1
    num_cols = (days_in_window + 6) // 7  # ceiling division
    # Don't force extra columns — padding will be added on the left during slicing

    # Fill grid
    grid: list[list[int | None]] = [[None for _ in range(num_cols)] for _ in range(ROWS)]
    values: list[list[Decimal | None]] = [[None for _ in range(num_cols)] for _ in range(ROWS)]

    for i in range(30):
        d = start + timedelta(days=i)
        d_str = d.isoformat()
        cost = costs.get(d_str)

        # Column = week offset from window_start
        col = (d - window_start).days // 7
        row = d.weekday()  # 0=Mon … 6=Sun

        if 0 <= col < num_cols and 0 <= row < ROWS:
            values[row][col] = cost

    # Compute thresholds (dynamic quartile when ≥10 data points, fixed-ratio otherwise)
    all_costs = [c for c in costs.values() if c > 0]
    t1, t2, t3 = _compute_level_thresholds(all_costs)

    # Assign levels
    today_col, today_row = None, None
    for row in range(ROWS):
        for col in range(num_cols):
            v = values[row][col]
            if v is None:
                grid[row][col] = None
            elif v == 0 or not all_costs:
                grid[row][col] = 0
            else:
                fv = float(v)
                if fv <= t1:
                    grid[row][col] = 1
                elif fv <= t2:
                    grid[row][col] = 2
                elif fv <= t3:
                    grid[row][col] = 3
                else:
                    grid[row][col] = 4

            # Check if this is today
            d = window_start + timedelta(days=col * 7 + row)
            if d == today:
                today_col = col
                today_row = row

    # Day labels (Chinese, Mon-Sun)
    day_labels = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    # Column header dates (first day of each week column)
    col_dates = []
    for col in range(num_cols):
        d = window_start + timedelta(days=col * 7)
        col_dates.append(d.strftime("%-m/%-d"))

    # Trim to exactly COLS columns centered on the data
    # Find first and last non-None column
    first_col = num_cols
    last_col = -1
    for row in range(ROWS):
        for col in range(num_cols):
            if grid[row][col] is not None:
                first_col = min(first_col, col)
                last_col = max(last_col, col)

    # Always right-align: today's column is the rightmost visible column
    end_col = last_col + 1
    start_col = end_col - COLS

    # Clamp end_col to actual data columns (start_col can be negative — left padding)
    if end_col > num_cols:
        end_col = num_cols
        start_col = end_col - COLS

    # Slice grid, values, col_dates to [start_col:end_col]
    sliced_grid = [[grid[row][col] if start_col <= col < end_col else None for col in range(COLS)] for row in range(ROWS)]
    # Remap to 0..COLS-1
    for row in range(ROWS):
        new_row = []
        for col in range(COLS):
            src_col = start_col + col
            if 0 <= src_col < num_cols:
                new_row.append(grid[row][src_col])
                # Check if this is today
                d = window_start + timedelta(days=src_col * 7 + row)
                if d == today:
                    today_col = col
                    today_row = row
            else:
                new_row.append(None)
        sliced_grid[row] = new_row

    sliced_values = [[values[row][start_col + col] if (0 <= start_col + col < num_cols) else None for col in range(COLS)] for row in range(ROWS)]
    sliced_dates = col_dates[start_col:end_col]

    # Recalculate today position in sliced grid
    today_col_sliced = None
    today_row_sliced = None
    for row in range(ROWS):
        for col in range(COLS):
            d = window_start + timedelta(days=(start_col + col) * 7 + row)
            if d == today:
                today_col_sliced = col
                today_row_sliced = row

    return (
        sliced_grid,
        sliced_values,
        day_labels,
        sliced_dates,
        today_col_sliced,
        today_row_sliced,
    )


# ---------------------------------------------------------------------------
# Canvas element helper (same pattern as layout.py)
# ---------------------------------------------------------------------------


def _element(
    el_type: str,
    tw: str = "",
    style: dict[str, Any] | None = None,
    children: Any = "",
    **extra: Any,
) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if tw:
        props["tw"] = tw
    if style:
        props["style"] = style
    if children or children == "":
        props["children"] = children
    props.update(extra)
    return {"type": el_type, "props": props}


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 4-column 28-day heatmap (for combined dashboard)
# ---------------------------------------------------------------------------
D4_CELL_W = 42
D4_CELL_H = 12
D4_GAP_X = 3
D4_GAP_Y = 3
D4_COLS = 4
D4_ROWS = 7
D4_GRID_W = D4_COLS * D4_CELL_W + (D4_COLS - 1) * D4_GAP_X  # 177
D4_GRID_H = D4_ROWS * D4_CELL_H + (D4_ROWS - 1) * D4_GAP_Y  # 102


def _render_4col_grid_png(
    grid: list[list[int | None]],  # [row][col]  heat level 0-4 or None
) -> bytes:
    """Render the 4×7 heatmap grid as a binary PNG with baked-in patterns."""
    pixels = [[255 for _ in range(D4_GRID_W)] for _ in range(D4_GRID_H)]

    for row in range(D4_ROWS):
        for col in range(D4_COLS):
            level = grid[row][col]
            x0 = col * (D4_CELL_W + D4_GAP_X)
            y0 = row * (D4_CELL_H + D4_GAP_Y)

            if level is None:
                continue

            for dy in range(D4_CELL_H):
                for dx in range(D4_CELL_W):
                    px, py = x0 + dx, y0 + dy
                    if not (0 <= px < D4_GRID_W and 0 <= py < D4_GRID_H):
                        continue
                    if dx < BORDER_PX or dx >= D4_CELL_W - BORDER_PX or dy < BORDER_PX or dy >= D4_CELL_H - BORDER_PX:
                        pixels[py][px] = 0  # black border
                    else:
                        ix = dx - BORDER_PX
                        iy = dy - BORDER_PX
                        iw = D4_CELL_W - 2 * BORDER_PX
                        ih = D4_CELL_H - 2 * BORDER_PX
                        if iw > 0 and ih > 0:
                            pixels[py][px] = _cell_pattern(ix, iy, level)

    return _make_grayscale_png(D4_GRID_W, D4_GRID_H, pixels)


def render_28day_heatmap(
    costs: dict[str, Decimal] | None = None,
    currency: str = "CNY",
) -> dict[str, Any]:
    """Render a 28-day (4-col × 7-row) heatmap for the combined dashboard.

    Returns a dict with keys:
        grid_uri, swatch_uris, total_str, avg_str, day_labels, col_dates,
        today_col, today_row, grid_w, grid_h, cell_w, cell_h, gap_x, gap_y
    """
    if costs is None:
        costs = gather_30day_costs()

    today = date.today()
    # Last column = current week (Mon-Sun), count back 3 weeks
    this_monday = today - timedelta(days=today.weekday())
    week0_monday = this_monday - timedelta(days=21)  # 3 weeks back = 4 weeks total
    window_start = week0_monday

    # Build 4-column grid
    grid: list[list[int | None]] = [[None for _ in range(D4_COLS)] for _ in range(D4_ROWS)]
    day_labels = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    # Compute thresholds (dynamic quartile when ≥10 data points, fixed-ratio otherwise)
    all_costs = [c for c in costs.values() if c > 0]
    t1, t2, t3 = _compute_level_thresholds(all_costs)

    today_col, today_row = None, None
    for i in range(28):
        d = window_start + timedelta(days=i)
        d_str = d.isoformat()
        cost = costs.get(d_str, Decimal("0"))

        col = (d - window_start).days // 7
        row = d.weekday()  # 0=Mon

        if 0 <= col < D4_COLS and 0 <= row < D4_ROWS:
            if d > today:
                grid[row][col] = None  # future → no fill
            elif cost == 0:
                grid[row][col] = 0
            elif all_costs:
                fv = float(cost)
                if fv <= t1:
                    grid[row][col] = 1
                elif fv <= t2:
                    grid[row][col] = 2
                elif fv <= t3:
                    grid[row][col] = 3
                else:
                    grid[row][col] = 4
            else:
                grid[row][col] = 0

            if d == today:
                today_col = col
                today_row = row

    # Column dates
    col_dates = []
    for col in range(D4_COLS):
        d = window_start + timedelta(days=col * 7)
        col_dates.append(d.strftime("%-m/%-d"))

    # Render PNG
    grid_uri = _png_to_data_uri(_render_4col_grid_png(grid))

    # Swatches
    swatch_uris = {}
    for level in range(5):
        swatch_uris[level] = _png_to_data_uri(_render_swatch_png(level))

    # Stats
    daily_list = [c for c in costs.values() if c > 0]
    total_cost = sum(daily_list, Decimal("0"))
    avg_cost = total_cost / max(len(daily_list), 1)
    total_str = _format_balance(total_cost, currency)
    avg_str = _format_balance(avg_cost, currency)

    return {
        "grid_uri": grid_uri,
        "swatch_uris": swatch_uris,
        "total_str": total_str,
        "avg_str": avg_str,
        "day_labels": day_labels,
        "col_dates": col_dates,
        "today_col": today_col,
        "today_row": today_row,
        "grid_w": D4_GRID_W,
        "grid_h": D4_GRID_H,
        "cell_w": D4_CELL_W,
        "cell_h": D4_CELL_H,
        "gap_x": D4_GAP_X,
        "gap_y": D4_GAP_Y,
    }


def build_heatmap_payload(
    costs: dict[str, Decimal] | None = None,
    currency: str = "CNY",
) -> dict[str, Any]:
    """Build the complete Canvas API payload for the heatmap view.

    Args:
        costs: If None, calls ``gather_30day_costs()`` automatically.
        currency: "CNY" or "USD".
    """
    if costs is None:
        costs = gather_30day_costs()

    (
        grid,
        values,
        day_labels,
        col_dates,
        today_col,
        today_row,
    ) = _assign_heat_levels(costs)

    # Render the grid as one PNG
    grid_png = _render_grid_png(grid)
    grid_uri = _png_to_data_uri(grid_png)

    # Render legend swatches
    swatch_uris = {}
    for level in range(5):
        swatch_uris[level] = _png_to_data_uri(_render_swatch_png(level))

    # Build date-range string from actual grid column span
    today = date.today()
    if col_dates:
        first_str = f"{today.year}/{col_dates[0]}"
        last_str = f"{today.year}/{col_dates[-1]}"
        try:
            first_dt = datetime.strptime(first_str, "%Y/%m/%d").date()
            last_dt = datetime.strptime(last_str, "%Y/%m/%d").date() + timedelta(days=6)
        except ValueError:
            first_dt = today - timedelta(days=29)
            last_dt = today
        date_range = f"{first_dt.strftime('%-m/%-d')} — {last_dt.strftime('%-m/%-d')}"
    else:
        start = today - timedelta(days=29)
        date_range = f"{start.strftime('%-m/%-d')} — {today.strftime('%-m/%-d')}"

    # Daily average and 30-day total
    daily_costs_list = [c for c in costs.values() if c > 0]
    total_cost = sum(daily_costs_list, Decimal("0"))
    avg_cost = total_cost / max(len(daily_costs_list), 1)
    avg_str = _format_balance(avg_cost, currency)
    total_str = _format_balance(total_cost, currency)

    # ---- Assemble payload ----
    children: list[dict[str, Any]] = []

    # Title row
    children.append(
        _element(
            "div",
            tw="flex flex-row items-center justify-between w-full",
            children=[
                _element("span", tw="text-14-chillksans font-bold", children="DeepSeek消费"),
                _element("span", tw="text-12-chillksans", children=date_range),
            ],
        )
    )

    # Spacer
    children.append(_element("div", tw="h-[2px] w-full"))

    # Column header row: empty space for day labels + week start dates
    header_cells: list[dict[str, Any]] = [
        _element("div", tw="w-[18px] shrink-0"),  # placeholder for day-label column
    ]
    for col in range(COLS):
        label = col_dates[col] if col < len(col_dates) else ""
        header_cells.append(
            _element(
                "div",
                tw=f"w-[{CELL_W}px] shrink-0 flex items-center justify-center",
                children=_element("span", tw="text-10-chillksans", children=label),
            )
        )
    children.append(
        _element(
            "div",
            tw="flex flex-row items-center w-full",
            style={"gap": f"{GAP_X}px"},
            children=header_cells,
        )
    )

    # Spacer
    children.append(_element("div", tw="h-[2px] w-full"))

    # Grid rows: day label + grid image
    # We render the FULL grid as one image and align day labels next to it.
    grid_row_height = CELL_H * ROWS + GAP_Y * (ROWS - 1)

    # Day labels column (7 rows matching grid)
    day_label_divs: list[dict[str, Any]] = []
    for r, label in enumerate(day_labels):
        day_label_divs.append(
            _element(
                "div",
                tw=f"w-[18px] h-[{CELL_H}px] shrink-0 flex items-center justify-center",
                children=_element("span", tw="text-12-chillksans", children=label),
            )
        )

    grid_row = _element(
        "div",
        tw="flex flex-row w-full",
        style={"gap": f"{GAP_X}px", "height": f"{grid_row_height}px"},
        children=[
            # Day labels
            _element(
                "div",
                tw="flex flex-col shrink-0",
                style={"gap": f"{GAP_Y}px", "height": f"{grid_row_height}px"},
                children=day_label_divs,
            ),
            # Grid image
            _element(
                "img",
                tw=f"w-[{GRID_W}px] h-[{GRID_H}px] img-dither-none img-levels-2",
                src=grid_uri,
            ),
        ],
    )
    children.append(grid_row)

    # Spacer
    children.append(_element("div", tw="h-[3px] w-full"))

    # Legend row
    legend_items: list[dict[str, Any]] = []
    for level in range(5):
        legend_items.append(
            _element(
                "img",
                tw="w-[12px] h-[12px] img-dither-none img-levels-2 shrink-0",
                src=swatch_uris[level],
            )
        )
    legend_items.append(
        _element("span", tw="text-11-chillksans shrink-0", children="低")
    )
    legend_items.append(
        _element("span", tw="text-11-chillksans shrink-0", children="→")
    )
    legend_items.append(
        _element("span", tw="text-11-chillksans shrink-0", children="高")
    )
    legend_items.append(
        _element(
            "span",
            tw="text-11-chillksans shrink-0",
            style={"marginLeft": "auto"},
            children=f"合计 {total_str} · 日均 {avg_str}",
        )
    )

    children.append(
        _element(
            "div",
            tw="flex flex-row items-center w-full",
            style={"gap": "3px"},
            children=legend_items,
        )
    )

    # Full page
    window_data = {
        "default": [
            _element(
                "div",
                tw="flex flex-col w-full h-full bg-white text-black",
                style={"padding": "4px 6px"},
                children=children,
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": "DeepSeek Heatmap",
        "border": 0,
        "link": "https://platform.deepseek.com",
        "layoutFull": {"tw": "p-0"},
        "windowData": window_data,
    }
