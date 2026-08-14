"""Recharge event logging — keeps daily consumption exact across recharges.

A balance delta alone can't distinguish "recharged ¥50, spent ¥1.77" from
"recharged ¥48.23" — both produce the same net balance increase. Recording
recharges explicitly lets delta-based cost calculations subtract them out:

    daily_cost = balance_before - balance_after + recharge_in_between

Two ways a recharge gets recorded:

1. **Manual** — ``--recharge 50 [--recharge-date 2026-08-13]``. The user runs
   this after topping up; retroactive records synthesize a noon timestamp,
   which lands in the snapshot interval ending on that date for typical daily
   snapshot cadences.
2. **Auto** — `detect_and_record_recharge` is called from ``save_snapshot``:
   the cron runs every 30 minutes, so a recharge shows up as a balance jump
   between two consecutive same-day snapshots. Spending within 30 minutes is
   a few cents, so the jump rounded to the nearest multiple of ¥10 is the
   recharge amount (user's stated pattern: recharges are multiples of 10).
   Cross-day jumps (offline overnight, recharge after the day's last run) are
   NOT auto-recorded — the jump may include a full day of spending; those
   fall back to the "balance went up" warning with a suggested amount.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path

logger = logging.getLogger(__name__)

RECHARGES_FILE = Path(__file__).resolve().parent.parent / "data" / "recharges.json"
_RETENTION_DAYS = 90

# Auto-detection thresholds (jump = new balance - previous balance).
# A jump >= 9.5 rounds to >= ¥10, the user's minimum recharge; smaller
# increases are logged (possible small refund/top-up) but not recorded.
AUTO_RECHARGE_MIN_JUMP = Decimal("9.5")
AUTO_RECHARGE_NOTICE_JUMP = Decimal("5")


@dataclass
class Recharge:
    amount: str  # Decimal as string, e.g. "50.00"
    date: str  # "YYYY-MM-DD" — day the recharge happened (user-facing)
    recorded_at: str  # ISO timestamp used to attribute it to a snapshot interval
    source: str = "manual"  # "manual" (--recharge) or "auto" (balance-jump detection)


@dataclass
class RechargeData:
    recharges: list[Recharge] = field(default_factory=list)


def load_recharges() -> RechargeData:
    """Load recharge records from disk. Returns empty data if file doesn't exist."""
    if not RECHARGES_FILE.exists():
        return RechargeData()

    try:
        raw = json.loads(RECHARGES_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return RechargeData()

    recharges = [
        Recharge(
            amount=r.get("amount", "0"),
            date=r.get("date", ""),
            recorded_at=r.get("recorded_at", ""),
            source=r.get("source", "manual"),
        )
        for r in raw.get("recharges", [])
    ]
    return RechargeData(recharges=recharges)


def save_recharges(data: RechargeData) -> None:
    """Persist recharge records, pruning to match history retention (90 days)."""
    cutoff = date.today().toordinal() - _RETENTION_DAYS
    kept = []
    for r in data.recharges:
        try:
            if date.fromisoformat(r.date).toordinal() > cutoff:
                kept.append(r)
        except ValueError:
            kept.append(r)  # unparseable date — keep rather than lose data

    RECHARGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "recharges": [
            {
                "amount": r.amount,
                "date": r.date,
                "recorded_at": r.recorded_at,
                "source": r.source,
            }
            for r in kept
        ],
    }
    RECHARGES_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), "utf-8")


def _round_to_10(v: Decimal) -> Decimal:
    """Round to the nearest multiple of 10 (user recharges in ¥10 increments).

    Used for auto-detection: the observed jump is the recharge minus a few
    cents of spend, so it approaches the recharge from below.
    """
    return (v / 10).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 10


def _ceil_to_10(v: Decimal) -> Decimal:
    """Round UP to the next multiple of 10 (used for warning suggestions)."""
    return (v / 10).to_integral_value(rounding=ROUND_CEILING) * 10


def _append_recharge(amount: Decimal, d: str, recorded_at: str, source: str) -> Recharge:
    rec = Recharge(amount=str(amount), date=d, recorded_at=recorded_at, source=source)
    data = load_recharges()
    data.recharges.append(rec)
    data.recharges.sort(key=lambda r: r.recorded_at)
    save_recharges(data)
    return rec


def record_recharge(amount: Decimal, date_str: str | None = None) -> Recharge:
    """Append a manual recharge record to disk and return it.

    ``date_str`` defaults to today (recorded_at = now). When given, the
    timestamp is synthesized as noon of that date for retroactive attribution.
    Replaces any auto-detected record for the same date (manual wins).
    """
    if date_str is None:
        d = date.today().isoformat()
        recorded_at = datetime.now().isoformat()
    else:
        d = date_str
        recorded_at = f"{date_str}T12:00:00"

    # Manual record supersedes auto-detected ones for the same date
    data = load_recharges()
    data.recharges = [
        r for r in data.recharges if not (r.date == d and r.source == "auto")
    ]
    save_recharges(data)

    return _append_recharge(amount, d, recorded_at, "manual")


def detect_and_record_recharge(
    prev_total: Decimal, new_total: Decimal
) -> Recharge | None:
    """Auto-detect a top-up from a balance jump between consecutive runs.

    Called from ``save_snapshot`` when a same-day snapshot already exists:
    consecutive runs are ~30 minutes apart (cron), so spending in between is
    negligible and the jump is ≈ the recharge amount. Rounds to the nearest
    multiple of ¥10 per the user's recharge pattern.
    """
    jump = new_total - prev_total
    if jump < AUTO_RECHARGE_MIN_JUMP:
        if jump >= AUTO_RECHARGE_NOTICE_JUMP:
            logger.info(
                "余额增加 ¥%s，低于自动充值记录阈值(¥10) — "
                "如为充值请手动运行 --recharge <金额>",
                jump,
            )
        return None

    amount = _round_to_10(jump)
    if amount < 10:
        return None

    rec = _append_recharge(amount, date.today().isoformat(), datetime.now().isoformat(), "auto")
    logger.warning(
        "检测到余额跳增 ¥%s，推测充值 ¥%s（四舍五入到10元整数倍），已自动记录 — "
        "如与实际不符请运行 ./run_balance_check.sh --recharge <实际金额> --recharge-date %s 修正",
        jump,
        amount,
        rec.date,
    )
    return rec


def estimate_recharge(positive_delta: Decimal) -> Decimal | None:
    """Suggest a recharge amount from a balance increase (for warnings).

    A warning's increase spans a full day or more, so the recharge must be
    >= the increase (spend can't be negative) — round UP to the next multiple
    of 10 (the minimum consistent amount). Returns None below ¥9.5.
    """
    if positive_delta < AUTO_RECHARGE_MIN_JUMP:
        return None
    return _ceil_to_10(positive_delta)


def recharge_sum_in_window(data: RechargeData, start_iso: str, end_iso: str) -> Decimal:
    """Sum recharges recorded in the half-open window ``(start_iso, end_iso]``.

    ``start_iso``/``end_iso`` are snapshot ``recorded_at`` timestamps (naive
    local ISO strings — lexicographic comparison is valid).
    """
    total = Decimal("0")
    for r in data.recharges:
        if r.recorded_at and start_iso < r.recorded_at <= end_iso:
            total += Decimal(r.amount)
    return total


def recharge_sum_since(data: RechargeData, since_iso: str) -> Decimal:
    """Sum recharges recorded after ``since_iso`` (up to now).

    Returns 0 when ``since_iso`` is empty (can't attribute without a boundary).
    """
    if not since_iso:
        return Decimal("0")
    total = Decimal("0")
    for r in data.recharges:
        if r.recorded_at and r.recorded_at > since_iso:
            total += Decimal(r.amount)
    return total


def recharge_sum_on_date(data: RechargeData, date_str: str) -> Decimal:
    """Sum recharges recorded for a specific date (fallback attribution)."""
    total = Decimal("0")
    for r in data.recharges:
        if r.date == date_str:
            total += Decimal(r.amount)
    return total
