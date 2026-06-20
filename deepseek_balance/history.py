"""Balance history persistence and consumption calculations."""

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


@dataclass
class Snapshot:
    date: str  # "YYYY-MM-DD"
    currency: str
    total_balance: str  # Stored as string for precision
    granted_balance: str
    topped_up_balance: str
    is_available: bool
    recorded_at: str  # ISO timestamp


@dataclass
class HistoryData:
    initial_recharge: float | None
    updated_at: str
    snapshots: list[Snapshot] = field(default_factory=list)


HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "balance_history.json"


def load_history() -> HistoryData:
    """Load balance history from disk. Returns empty history if file doesn't exist."""
    if not HISTORY_FILE.exists():
        return HistoryData(initial_recharge=None, updated_at="")

    try:
        raw = json.loads(HISTORY_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # Backup corrupted file
        backup = HISTORY_FILE.with_suffix(".json.bak")
        shutil.copy2(HISTORY_FILE, backup)
        print(f"[WARN] Corrupted history file backed up to {backup}: {e}")
        return HistoryData(initial_recharge=None, updated_at="")

    snapshots = []
    for s in raw.get("snapshots", []):
        snapshots.append(Snapshot(
            date=s.get("date", ""),
            currency=s.get("currency", ""),
            total_balance=s.get("total_balance", "0"),
            granted_balance=s.get("granted_balance", "0"),
            topped_up_balance=s.get("topped_up_balance", "0"),
            is_available=s.get("is_available", True),
            recorded_at=s.get("recorded_at", ""),
        ))

    return HistoryData(
        initial_recharge=raw.get("initial_recharge"),
        updated_at=raw.get("updated_at", ""),
        snapshots=snapshots,
    )


def save_snapshot(
    history: HistoryData,
    total_balance: Decimal,
    currency: str,
    granted_balance: Decimal,
    topped_up_balance: Decimal,
    is_available: bool,
    initial_recharge: float | None,
) -> None:
    """Save today's balance snapshot, replacing existing same-date entry."""
    today_str = date.today().isoformat()
    now_iso = datetime.now().isoformat()

    new_snapshot = Snapshot(
        date=today_str,
        currency=currency,
        total_balance=str(total_balance),
        granted_balance=str(granted_balance),
        topped_up_balance=str(topped_up_balance),
        is_available=is_available,
        recorded_at=now_iso,
    )

    # Replace existing same-date snapshot, or append
    replaced = False
    for i, s in enumerate(history.snapshots):
        if s.date == today_str:
            history.snapshots[i] = new_snapshot
            replaced = True
            break
    if not replaced:
        history.snapshots.append(new_snapshot)

    # Sort by date ascending (oldest first)
    history.snapshots.sort(key=lambda s: s.date)
    history.updated_at = now_iso
    history.initial_recharge = initial_recharge

    # Prune to last 90 days
    if len(history.snapshots) > 90:
        history.snapshots = history.snapshots[-90:]

    # Ensure data directory exists
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    raw = {
        "initial_recharge": history.initial_recharge,
        "updated_at": history.updated_at,
        "snapshots": [
            {
                "date": s.date,
                "currency": s.currency,
                "total_balance": s.total_balance,
                "granted_balance": s.granted_balance,
                "topped_up_balance": s.topped_up_balance,
                "is_available": s.is_available,
                "recorded_at": s.recorded_at,
            }
            for s in history.snapshots
        ],
    }
    HISTORY_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), "utf-8")


def get_latest_balance(history: HistoryData) -> Decimal | None:
    """Get the most recent balance from history snapshots."""
    if not history.snapshots:
        return None
    return Decimal(history.snapshots[-1].total_balance)


def get_yesterday_balance(history: HistoryData) -> Decimal | None:
    """Get yesterday's balance from history snapshots."""
    yesterday = date.today().isoformat()
    # yesterday is a date string, but we need the actual previous day
    # So we check if there's a snapshot from the day before today
    # Actually, let me keep it simple: find the snapshot with the date before today
    today_str = date.today().isoformat()
    for s in reversed(history.snapshots):
        if s.date < today_str:
            return Decimal(s.total_balance)
    return None


def compute_daily_consumption(
    today_balance: Decimal, yesterday_balance: Decimal | None
) -> Decimal | None:
    """Calculate daily consumption: yesterday - today (positive = spent).

    Returns None if no yesterday data available (first run).
    """
    if yesterday_balance is None:
        return None
    return yesterday_balance - today_balance


def compute_total_spent(
    today_balance: Decimal, initial_recharge: float | None
) -> Decimal | None:
    """Calculate total spent: initial_recharge - current_balance.

    Returns None if no initial_recharge is configured.
    """
    if initial_recharge is None:
        return None
    return Decimal(str(initial_recharge)) - today_balance
