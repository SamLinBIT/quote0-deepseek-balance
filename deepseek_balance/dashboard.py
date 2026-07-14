"""Combined dashboard: DeepSeek balance (left) + 28-day heatmap (right).

Pushes as a single Canvas payload with a two-column layout mimicking the
existing balance view on the left and a 4-week heatmap on the right.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from deepseek_balance.layout import _format_balance
from deepseek_balance.heatmap import render_28day_heatmap


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


def build_dashboard_payload(
    *,
    balance_display: str,
    currency: str,
    is_available: bool,
    status_text: str,
    error_message: str | None = None,
    timestamp: str = "",
    costs: dict[str, Decimal] | None = None,
    thresholds: tuple[float, float, float] = (1.0, 2.0, 3.0),
) -> dict[str, Any]:
    """Build the combined dashboard Canvas payload.

    Args:
        balance_display: Formatted balance string (e.g. "¥20.55").
        currency: "CNY" or "USD".
        is_available: Whether the DeepSeek balance API returned successfully.
        status_text: "✓ Active" / "✗ Unavailable".
        error_message: If set, show error overlay on the left side.
        timestamp: "MM/DD HH:MM" string.
        costs: 28-day cost data dict; if None, gathered automatically.
    """
    # ---- Heatmap data ----
    hm = render_28day_heatmap(costs, currency, thresholds)

    # ---- Left column ----
    left_children: list[dict[str, Any]] = []

    # Icon
    icon_tw = "w-[50px] h-[50px] img-dither-none img-levels-4"
    if error_message:
        icon_tw += " opacity-40"

    left_children.append(
        _element(
            "img",
            tw=icon_tw,
            src="https://cdn.deepseek.com/platform/favicon.png",
        )
    )

    # Status
    left_children.append(
        _element("span", tw="text-14-chillksans", children=status_text)
    )

    # Timestamp
    left_children.append(
        _element(
            "span",
            tw="text-12-chillksans",
            style={"whiteSpace": "nowrap"},
            children=timestamp,
        )
    )

    # Balance
    if error_message:
        left_children.append(
            _element(
                "div",
                tw="flex flex-col items-center gap-[1px]",
                children=[
                    _element(
                        "span",
                        tw="text-18-chillksans font-bold",
                        children=balance_display,
                    ),
                    _element(
                        "span",
                        tw="text-10-chillksans",
                        style={
                            "overflow": "hidden",
                            "textOverflow": "ellipsis",
                            "whiteSpace": "pre-wrap",
                            "wordBreak": "break-word",
                            "lineClamp": 2,
                        },
                        children=error_message,
                    ),
                ],
            )
        )
    else:
        left_children.append(
            _element(
                "span",
                tw="text-18-chillksans font-bold",
                children=balance_display,
            )
        )

    left_column = _element(
        "div",
        tw="flex flex-col items-center justify-center w-[70px] h-full shrink-0 gap-[2px]",
        children=left_children,
    )

    # ---- Right column (heatmap) ----
    right_children: list[dict[str, Any]] = []

    # Column header row — paddingLeft matches day-label column width
    header_cells = []
    for col in range(4):
        label = hm["col_dates"][col] if col < len(hm["col_dates"]) else ""
        header_cells.append(
            _element(
                "div",
                tw=f"w-[{hm['cell_w']}px] shrink-0 flex items-center justify-center",
                children=_element("span", tw="text-pixel-10", children=label),
            )
        )
    right_children.append(
        _element(
            "div",
            tw="flex flex-row items-center w-full",
            style={"paddingLeft": f"{18 + hm['gap_x']}px", "gap": f"{hm['gap_x']}px"},
            children=header_cells,
        )
    )

    # Spacer
    right_children.append(_element("div", tw="h-[2px] w-full"))

    # Grid row: day labels + grid image
    day_label_divs: list[dict[str, Any]] = []
    for label in hm["day_labels"]:
        day_label_divs.append(
            _element(
                "div",
                tw=f"w-[18px] h-[{hm['cell_h']}px] shrink-0 flex items-center justify-center",
                children=_element("span", tw="text-12-chillksans", children=label),
            )
        )

    grid_row_height = hm["grid_h"]
    right_children.append(
        _element(
            "div",
            tw="flex flex-row w-full",
            style={"gap": f"{hm['gap_x']}px", "height": f"{grid_row_height}px"},
            children=[
                _element(
                    "div",
                    tw="flex flex-col shrink-0",
                    style={"gap": f"{hm['gap_y']}px", "height": f"{grid_row_height}px"},
                    children=day_label_divs,
                ),
                _element(
                    "img",
                    tw=f"w-[{hm['grid_w']}px] h-[{hm['grid_h']}px] img-dither-none img-levels-2",
                    src=hm["grid_uri"],
                ),
            ],
        )
    )

    # Spacer
    right_children.append(_element("div", tw="h-[2px] w-full"))

    # Today's cost
    from datetime import date
    today_str = date.today().isoformat()
    today_cost = costs.get(today_str, Decimal("0")) if costs else Decimal("0")
    today_cost_str = _format_balance(today_cost, currency)

    # Legend row (swatches + today's cost only)
    legend_items: list[dict[str, Any]] = []
    for level in range(5):
        legend_items.append(
            _element(
                "img",
                tw="w-[12px] h-[12px] img-dither-none img-levels-2 shrink-0",
                src=hm["swatch_uris"][level],
            )
        )
    legend_items.append(
        _element(
            "span",
            tw="text-12-chillksans font-bold shrink-0",
            style={"marginLeft": "auto"},
            children=f"今日 {today_cost_str}",
        )
    )
    right_children.append(
        _element(
            "div",
            tw="flex flex-row items-center w-full",
            style={"gap": "3px"},
            children=legend_items,
        )
    )

    right_column = _element(
        "div",
        tw="flex flex-col flex-1 min-w-0 justify-center gap-[2px]",
        children=right_children,
    )

    # ---- Assemble ----
    window_data = {
        "default": [
            _element(
                "div",
                tw="flex flex-row w-full h-full min-w-0 min-h-0 bg-white text-black gap-[12px]",
                children=[left_column, right_column],
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": "DeepSeek Dashboard",
        "border": 0,
        "link": "https://platform.deepseek.com",
        "layoutFull": {"tw": "p-[8px]"},
        "windowData": window_data,
    }
