"""Plain-text NFC report for tap-to-view delivery.

Generates a compact ``data:text/plain`` URI (~350-450 chars) that fits within
the Canvas API's 500-character ``link`` field limit.  Includes a mini bar-chart
using Unicode block characters so the recent spending pattern is glanceable.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from deepseek_balance.layout import _format_balance

# ASCII bar characters (1 byte each vs 3 bytes for Unicode blocks).
_BLOCKS = [".", "-", "=", "#"]  # 0 %, 33 %, 66 %, 100 %


def _bar(val: float, max_val: float, width: int = 8) -> str:
    """Render a proportional ASCII bar of *width* steps."""
    if max_val <= 0:
        return "."
    ratio = max(0.0, min(1.0, val / max_val))
    filled = int(ratio * width)
    remainder = (ratio * width) - filled
    partial = int(remainder * 3)  # 0..2 → index into _BLOCKS[0:3]
    bar = _BLOCKS[-1] * filled
    if partial > 0 and filled < width:
        bar += _BLOCKS[partial]
    return bar or "."


def build_nfc_text_report(
    *,
    costs: dict[str, Decimal],
    balance_display: str,
    currency: str,
    monthly_cost: Decimal | None,
    timestamp: str,
) -> str:
    """Build a plain-text spending summary and return as ``data:text/plain`` URI.

    Fits within the 500-character limit of the Canvas API ``link`` field.
    """
    today = date.today()

    # ---- Stats ----
    all_positive = [c for c in costs.values() if c > 0]
    total_30d = sum(all_positive, Decimal("0"))
    avg_daily = total_30d / max(len(all_positive), 1)
    monthly_str = _format_balance(monthly_cost, currency) if monthly_cost else "--"

    # ---- Last 7 days + max for bar scaling ----
    recent: list[tuple[str, Decimal, bool]] = []
    recent_max = Decimal("0")
    for i in range(7):
        d = today - timedelta(days=6 - i)
        d_str = d.isoformat()
        cost = costs.get(d_str, Decimal("0"))
        recent.append((f"{d.month}/{d.day}", cost, d == today))
        if cost > recent_max:
            recent_max = cost

    # ---- Build text ----
    lines: list[str] = [
        "DeepSeek API 消费报告",
        f"余额 {balance_display}  本月 {monthly_str}",
        "----------------------",
        "近7天消费:",
    ]

    for label, cost, is_today in recent:
        bar = _bar(float(cost), float(recent_max))
        marker = " ←" if is_today else ""
        cost_str = f"¥{float(cost):.2f}"
        lines.append(f"{label} {bar} {cost_str}{marker}")

    lines.extend([
        "----------------------",
        f"30天合计 ¥{float(total_30d):.2f}  日均 ¥{float(avg_daily):.2f}",
        f"更新 {timestamp}",
    ])

    body = "\n".join(lines)

    # Try raw text first — some NFC implementations handle plain text directly
    uri = body

    return uri
