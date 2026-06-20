"""Canvas API windowData JSON builder for 296x152 e-ink screen."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def _cny(v: Decimal) -> str:
    """Format a Decimal as CNY currency string."""
    return f"¥{v:,.2f}"


def _usd(v: Decimal) -> str:
    """Format a Decimal as USD currency string."""
    return f"${v:,.2f}"


def _format_balance(v: Decimal, currency: str) -> str:
    if currency == "USD":
        return _usd(v)
    return _cny(v)


def _format_change(v: Decimal | None, currency: str) -> str:
    """Format a daily change value (absolute, no sign)."""
    if v is None:
        return "--.--"
    return _format_balance(abs(v), currency)


def _format_monthly_cost(v: Decimal | None, currency: str) -> str | None:
    if v is None:
        return None
    fmt = _format_balance(abs(v), currency)
    return f"本月消费 {fmt}"


def _element(
    el_type: str,
    tw: str = "",
    style: dict[str, Any] | None = None,
    children: Any = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build a Canvas element dict."""
    props: dict[str, Any] = {}
    if tw:
        props["tw"] = tw
    if style:
        props["style"] = style
    if children or children == "":
        props["children"] = children
    props.update(extra)
    return {"type": el_type, "props": props}


def build_canvas_payload(
    *,
    balance_display: str,
    currency: str,
    daily_change: Decimal | None,
    is_available: bool,
    status_text: str,
    error_message: str | None = None,
    initial_recharge: float | None = None,
    timestamp: str = "",
    last_balance_display: str | None = None,
    monthly_consumption: Decimal | None = None,
) -> dict[str, Any]:
    """Build the complete Canvas API request payload."""

    if error_message:
        return _build_error_payload(error_message, timestamp, last_balance_display)

    # Build right-side info rows
    right_children: list[dict[str, Any]] = []

    # Row 1: "DeepSeek Balance" title
    right_children.append(
        _element("div",
            tw="flex flex-row items-center gap-[2px] text-18-chillksans",
            children=[
                _element("span", tw="font-bold", children="DeepSeek Balance"),
            ],
        )
    )

    # Row 2: Large balance number
    cny_display = balance_display
    right_children.append(
        _element("div",
            tw="text-28-chillksans font-bold leading-[1]",
            style={
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            children=cny_display,
        )
    )

    # Row 3: Daily change
    daily_str = _format_change(daily_change, currency)
    daily_sign = ""
    if daily_change is not None:
        daily_sign = "↓" if daily_change > 0 else "↑" if daily_change < 0 else "→"

    right_children.append(
        _element("div",
            tw="flex flex-row items-center gap-[2px] text-18-chillksans",
            style={
                "overflow": "hidden",
                "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            },
            children=[
                _element("span", children="今日"),
                _element("span", children=f"{daily_sign} {daily_str}".strip()),
            ],
        )
    )

    # Row 4: Monthly consumption
    monthly_str = _format_monthly_cost(monthly_consumption, currency)
    if monthly_str:
        right_children.append(
            _element("div",
                tw="text-18-chillksans",
                style={
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                    "whiteSpace": "nowrap",
                },
                children=monthly_str,
            )
        )

    window_data = {
        "default": [
            _element("div",
                tw="flex flex-row w-full h-full min-w-0 min-h-0 bg-white text-black gap-[6px]",
                children=[
                    # Left: Icon column with status below
                    _element("div",
                        tw="flex flex-col items-center justify-center w-[100px] h-full shrink-0 gap-[2px]",
                        children=[
                            _element("img",
                                tw="w-[75px] h-[75px] img-dither-none img-levels-4",
                                src="https://cdn.deepseek.com/platform/favicon.png",
                            ),
                            _element("span",
                                tw="text-14-chillksans",
                                children=status_text,
                            ),
                            _element("span",
                                tw="text-12-chillksans",
                                children=timestamp,
                            ),
                        ],
                    ),
                    # Right: Info column
                    _element("div",
                        tw="flex flex-col flex-1 min-w-0 justify-center gap-[2px]",
                        children=right_children,
                    ),
                ],
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": "DeepSeek Balance",
        "border": 0,
        "layoutFull": {"tw": "p-[8px]"},
        "windowData": window_data,
    }


def _build_error_payload(
    error_message: str,
    timestamp: str = "",
    last_balance_display: str | None = None,
) -> dict[str, Any]:
    """Build an error-state Canvas payload to show on the device."""
    window_data = {
        "default": [
            _element("div",
                tw="flex flex-row w-full h-full min-w-0 min-h-0 bg-white text-black gap-[6px]",
                children=[
                    # Left: Dimmed icon with status below
                    _element("div",
                        tw="flex flex-col items-center justify-center w-[100px] h-full shrink-0 gap-[2px]",
                        children=[
                            _element("img",
                                tw="w-[75px] h-[75px] img-dither-none img-levels-2 opacity-40",
                                src="https://cdn.deepseek.com/platform/favicon.png",
                            ),
                            _element("span",
                                tw="text-14-chillksans",
                                children="✗ Offline",
                            ),
                            _element("span",
                                tw="text-12-chillksans",
                                children=timestamp,
                            ),
                        ],
                    ),
                    # Right: Error info
                    _element("div",
                        tw="flex flex-col flex-1 min-w-0 justify-center gap-[2px]",
                        children=[
                            _element("div",
                                tw="flex flex-row items-center gap-[2px] text-18-chillksans",
                                children=[
                                    _element("span", tw="font-bold", children="DeepSeek Balance"),
                                ],
                            ),
                            _element("div",
                                tw="text-28-chillksans font-bold leading-[1]",
                                style={
                                    "overflow": "hidden",
                                    "textOverflow": "ellipsis",
                                    "whiteSpace": "nowrap",
                                },
                                children=last_balance_display or "--.--",
                            ),
                            _element("div",
                                tw="text-18-chillksans",
                                style={
                                    "overflow": "hidden",
                                    "textOverflow": "ellipsis",
                                    "whiteSpace": "pre-wrap",
                                    "wordBreak": "break-word",
                                    "lineClamp": 3,
                                },
                                children=error_message,
                            ),
                        ],
                    ),
                ],
            ),
        ],
    }

    return {
        "refreshNow": True,
        "taskAlias": "DeepSeek Balance",
        "border": 0,
        "layoutFull": {"tw": "p-[8px]"},
        "windowData": window_data,
    }
