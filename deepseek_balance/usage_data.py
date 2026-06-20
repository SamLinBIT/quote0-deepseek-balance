"""Usage cost data management for monthly consumption tracking."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

USAGE_FILE = Path(__file__).resolve().parent.parent / "data" / "usage_history.json"


@dataclass
class UsageData:
    monthly_cost: dict[str, str] = field(default_factory=dict)  # "YYYY-MM" -> "10.50"
    last_updated_date: str = ""  # "YYYY-MM-DD"
    imported_daily_costs: dict[str, str] = field(default_factory=dict)  # "YYYY-MM-DD" -> "0.43"


def load_usage() -> UsageData:
    """Load usage history from disk. Returns empty data if file doesn't exist."""
    if not USAGE_FILE.exists():
        return UsageData()

    try:
        raw = json.loads(USAGE_FILE.read_text("utf-8"))
    except (json.JSONDecodeError, OSError):
        return UsageData()

    return UsageData(
        monthly_cost=raw.get("monthly_cost", {}),
        last_updated_date=raw.get("last_updated_date", ""),
        imported_daily_costs=raw.get("imported_daily_costs", {}),
    )


def save_usage(data: UsageData) -> None:
    """Persist usage data to disk."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "monthly_cost": data.monthly_cost,
        "last_updated_date": data.last_updated_date,
        "imported_daily_costs": data.imported_daily_costs,
    }
    USAGE_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2), "utf-8")


def import_cost_csv(zip_path: str | Path) -> tuple[dict[str, Decimal], Decimal, str]:
    """Import cost data from a DeepSeek usage zip.

    Reads `cost-YYYY-M.csv` from the zip, aggregates costs by day.

    Returns:
        daily_costs: dict of date string -> Decimal cost
        monthly_total: sum of all costs in the CSV
        last_date: latest date string found in the CSV ("YYYY-MM-DD")
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    daily_costs: dict[str, Decimal] = {}
    last_date = ""

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Find the cost CSV file
        cost_files = [n for n in zf.namelist() if n.startswith("cost-") and n.endswith(".csv")]
        if not cost_files:
            raise ValueError(f"No cost-*.csv found in {zip_path}")

        for cost_file in cost_files:
            raw = zf.read(cost_file).decode("utf-8-sig")  # Handle BOM
            reader = csv.DictReader(io.StringIO(raw))
            for row in reader:
                utc_date = row.get("utc_date", "").strip()
                cost_str = row.get("cost", "0").strip()
                if not utc_date:
                    continue
                cost = Decimal(cost_str)
                daily_costs[utc_date] = daily_costs.get(utc_date, Decimal("0")) + cost
                if utc_date > last_date:
                    last_date = utc_date

    monthly_total = sum(daily_costs.values(), Decimal("0"))

    return daily_costs, monthly_total, last_date


def seed_monthly_cost(usage: UsageData, daily_costs: dict[str, Decimal], monthly_total: Decimal, last_date: str) -> None:
    """Seed usage data from an imported cost CSV.

    Stores the monthly total and daily breakdown, tagged with the last date covered.
    """
    year_month = last_date[:7]  # "YYYY-MM"

    # Convert Decimals to strings for JSON
    usage.monthly_cost[year_month] = str(monthly_total)
    usage.last_updated_date = last_date
    for d, cost in daily_costs.items():
        usage.imported_daily_costs[d] = str(cost)


def get_daily_cost(usage: UsageData, date_str: str) -> Decimal | None:
    """Get the cost for a specific date from imported data.

    Returns None if no cost data exists for that date.
    """
    val = usage.imported_daily_costs.get(date_str)
    if val is None:
        return None
    return Decimal(val)


def get_monthly_consumption(usage: UsageData, year_month: str) -> Decimal | None:
    """Get month-to-date consumption for the given month.

    Returns None if no data exists for this month.
    """
    val = usage.monthly_cost.get(year_month)
    if val is None:
        return None
    return Decimal(val)


def update_monthly_consumption(
    usage: UsageData,
    daily_change: Decimal,
    yesterday_date: str,  # "YYYY-MM-DD"
) -> None:
    """Add a day's consumption to the monthly total.

    Uses yesterday_date to prevent double-counting: only accumulates
    when the spending date (yesterday) is after the last updated date.

    Handles month rollover: if the current month differs from the stored
    month, starts a fresh monthly total.
    """
    if daily_change <= 0:
        return  # No consumption or net refund — don't accumulate

    today = date.today()
    year_month = today.strftime("%Y-%m")

    # Guard: only add if yesterday's spending is newer than last update
    if yesterday_date <= usage.last_updated_date:
        return

    # Month rollover: start fresh
    current = Decimal(usage.monthly_cost.get(year_month, "0"))

    usage.monthly_cost[year_month] = str(current + daily_change)
    usage.last_updated_date = yesterday_date
