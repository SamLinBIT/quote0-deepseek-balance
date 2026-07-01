"""DeepSeek balance dashboard orchestrator.

Usage:
    python -m deepseek_balance.main           # Full run (fetch + save + push)
    python -m deepseek_balance.main --dry-run # Print payload without pushing
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

from deepseek_balance.config import load_config
from deepseek_balance.balance_api import (
    fetch_balance,
    DeepSeekError,
    DeepSeekAuthError,
    DeepSeekNetworkError,
    DeepSeekParseError,
)
from deepseek_balance.history import (
    load_history,
    save_snapshot,
    get_yesterday_balance,
    compute_daily_consumption,
)
from deepseek_balance.layout import build_canvas_payload, _format_balance, _format_change
from deepseek_balance.usage_data import (
    load_usage,
    save_usage,
    import_cost_csv,
    seed_monthly_cost,
    get_daily_cost,
    get_monthly_consumption,
    update_monthly_consumption,
)
from deepseek_balance.heatmap import gather_30day_costs, build_heatmap_payload
from deepseek_balance.dashboard import build_dashboard_payload

from deepseek_balance.dot_push import (
    push_canvas,
    DotPushError,
    DotAuthError,
    DotDeviceNotFoundError,
    DotValidationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DeepSeek balance dashboard for Quote/0"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Canvas payload to stdout without pushing to device",
    )
    parser.add_argument(
        "--import-usage",
        type=str,
        metavar="ZIP",
        help="Import monthly cost data from a DeepSeek usage zip (e.g. usage_data_2026_6.zip)",
    )
    parser.add_argument(
        "--heatmap",
        action="store_true",
        help="Push 30-day spending heatmap to device (separate view from balance dashboard)",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Push combined dashboard (balance + 28-day heatmap) to device",
    )
    args = parser.parse_args()

    # Handle --import-usage (one-time data import)
    if args.import_usage:
        return _handle_import_usage(args.import_usage)

    # 1. Load config
    config = load_config()
    logger.info("Configuration loaded")
    logger.info("Currency preference: %s", config.currency)

    # 1a. Handle --heatmap and --dashboard (separate views)
    if args.heatmap:
        return _handle_heatmap(args, config)
    if args.dashboard:
        return _handle_dashboard(args, config)

    timestamp = datetime.now().strftime("%-m/%-d %H:%M")

    # 2. Load history (always, for both normal display and error fallback)
    history = load_history()
    logger.info("History loaded: %d snapshots", len(history.snapshots))

    # 3. Fetch DeepSeek balance
    error_message: str | None = None
    balance = None

    try:
        balance = fetch_balance(config.deepseek_api_key)
        logger.info(
            "Balance fetched: %s %s (available=%s)",
            balance.currency,
            balance.total_balance,
            balance.is_available,
        )
    except DeepSeekAuthError as e:
        logger.error("DeepSeek auth error: %s", e)
        error_message = "Invalid DeepSeek API key"
    except DeepSeekParseError as e:
        logger.error("DeepSeek parse error: %s", e)
        error_message = "Invalid balance data received"
    except DeepSeekNetworkError as e:
        logger.error("DeepSeek network error: %s", e)
        error_message = "DeepSeek service unavailable"
    except DeepSeekError as e:
        logger.error("DeepSeek error: %s", e)
        error_message = f"Error: {e}"

    if error_message or balance is None:
        # Extract last known balance for error display
        last_balance_display = None
        if history.snapshots:
            last = history.snapshots[-1]
            last_val = _format_balance(Decimal(last.total_balance), config.currency)
            short_date = last.date[-5:].replace("-", "/")  # "06/19"
            last_balance_display = f"{last_val} ({short_date})"

        # Build error payload and push
        payload = build_canvas_payload(
            balance_display="--.--",
            currency=config.currency,
            daily_change=None,
            is_available=False,
            status_text="✗ Offline",
            error_message=error_message or "Unknown error",
            initial_recharge=config.initial_recharge,
            timestamp=timestamp,
            last_balance_display=last_balance_display,
        )
        return _handle_push(args, config, payload, "error state")

    # 4. Calculate consumption
    snapshot_count = len(history.snapshots)

    # Load usage data
    usage = load_usage()
    year_month = datetime.now().strftime("%Y-%m")
    monthly_consumption = get_monthly_consumption(usage, year_month)

    # Prefer CSV daily cost for today, fall back to balance delta
    today_str = date.today().isoformat()
    csv_daily = get_daily_cost(usage, today_str)
    if csv_daily is not None and csv_daily > 0:
        daily_consumption = csv_daily
        yesterday_balance = None
        logger.info("Daily cost (from usage data): %s %s", balance.currency, daily_consumption)
    else:
        yesterday_balance = get_yesterday_balance(history)
        daily_consumption = compute_daily_consumption(
            balance.total_balance, yesterday_balance
        )
        if yesterday_balance is not None:
            logger.info("Yesterday balance: %s %s", balance.currency, yesterday_balance)
            logger.info("Daily consumption (from balance delta): %s %s", balance.currency, daily_consumption)
        else:
            logger.info("No historical data — daily consumption unavailable")

    logger.info("Current balance: %s %s", balance.currency, balance.total_balance)
    if monthly_consumption is not None:
        logger.info("Monthly consumption: %s %s", balance.currency, monthly_consumption)

    # 5. Save snapshot BEFORE pushing (data > display)
    save_snapshot(
        history=history,
        total_balance=balance.total_balance,
        currency=balance.currency,
        granted_balance=balance.granted_balance,
        topped_up_balance=balance.topped_up_balance,
        is_available=balance.is_available,
        initial_recharge=config.initial_recharge,
    )
    logger.info("Snapshot saved")

    # 5a. Update monthly consumption from daily delta
    if daily_consumption is not None and daily_consumption > 0 and yesterday_balance is not None:
        yesterday_str = (date.today() - timedelta(days=1)).isoformat()
        update_monthly_consumption(usage, daily_consumption, yesterday_str)
        save_usage(usage)
        monthly_consumption = get_monthly_consumption(usage, year_month)

    # 6. Build Canvas payload
    balance_display = _format_balance(balance.total_balance, config.currency)
    status_text = "✓ Active" if balance.is_available else "✗ Unavailable"

    payload = build_canvas_payload(
        balance_display=balance_display,
        currency=config.currency,
        daily_change=daily_consumption,
        monthly_consumption=monthly_consumption,
        is_available=balance.is_available,
        status_text=status_text,
        error_message=None,
        initial_recharge=config.initial_recharge,
        timestamp=timestamp,
    )

    # 7. Push to device
    return _handle_push(args, config, payload, "dashboard")


def _handle_heatmap(args: argparse.Namespace, config) -> int:
    """Gather 30-day cost data and push the heatmap to the device."""
    logger.info("Gathering 30-day cost data for heatmap...")
    costs = gather_30day_costs()
    logger.info("Collected cost data for %d days", len(costs))

    payload = build_heatmap_payload(costs, config.currency)
    return _handle_push(args, config, payload, "heatmap")


def _handle_dashboard(args: argparse.Namespace, config) -> int:
    """Fetch balance, gather 28-day costs, and push the combined dashboard."""
    timestamp = datetime.now().strftime("%-m/%-d %H:%M")

    # Always load history (needed for error fallback AND for saving snapshots)
    history = load_history()
    logger.info("History loaded: %d snapshots", len(history.snapshots))

    # Load usage data (for daily cost tracking)
    usage = load_usage()

    if args.dry_run:
        # Use placeholder balance data — no API calls
        balance_display = _format_balance(Decimal("20.55"), config.currency)
        is_available = True
        status_text = "✓ Active"
        error_message = None
        balance = None
    else:
        from deepseek_balance.balance_api import (
            fetch_balance,
            DeepSeekError,
            DeepSeekAuthError,
            DeepSeekNetworkError,
            DeepSeekParseError,
        )

        error_message = None
        balance = None
        balance_display = None
        is_available = False

        try:
            balance = fetch_balance(config.deepseek_api_key)
            logger.info("Balance fetched: %s %s", balance.currency, balance.total_balance)
            balance_display = _format_balance(balance.total_balance, config.currency)
            is_available = balance.is_available
        except DeepSeekAuthError as e:
            logger.error("DeepSeek auth error: %s", e)
            error_message = "Invalid DeepSeek API key"
        except DeepSeekParseError as e:
            logger.error("DeepSeek parse error: %s", e)
            error_message = "Invalid balance data received"
        except DeepSeekNetworkError as e:
            logger.error("DeepSeek network error: %s", e)
            error_message = "DeepSeek service unavailable"
        except DeepSeekError as e:
            logger.error("DeepSeek error: %s", e)
            error_message = f"Error: {e}"

        if error_message or balance is None:
            if history.snapshots:
                last = history.snapshots[-1]
                last_val = _format_balance(Decimal(last.total_balance), config.currency)
                short_date = last.date[-5:].replace("-", "/")
                balance_display = f"{last_val} ({short_date})"
            else:
                balance_display = "--.--"

        status_text = "✓ Active" if (balance and balance.is_available) else "✗ Offline"

    # Save snapshot to balance_history.json (only when we have fresh data)
    if not args.dry_run and balance is not None:
        save_snapshot(
            history=history,
            total_balance=balance.total_balance,
            currency=balance.currency,
            granted_balance=balance.granted_balance,
            topped_up_balance=balance.topped_up_balance,
            is_available=balance.is_available,
            initial_recharge=config.initial_recharge,
        )
        logger.info("Snapshot saved")

        # Update monthly consumption from balance delta
        yesterday_balance = get_yesterday_balance(history)
        if yesterday_balance is not None:
            daily_consumption = compute_daily_consumption(
                balance.total_balance, yesterday_balance
            )
            if daily_consumption is not None and daily_consumption > 0:
                yesterday_str = (date.today() - timedelta(days=1)).isoformat()
                update_monthly_consumption(usage, daily_consumption, yesterday_str)
                save_usage(usage)
                logger.info("Usage data updated")

    # Gather 28-day costs (now includes the fresh snapshot we just saved)
    costs = gather_30day_costs()

    # Build payload
    payload = build_dashboard_payload(
        balance_display=balance_display or "--.--",
        currency=config.currency,
        is_available=is_available,
        status_text=status_text,
        error_message=error_message,
        timestamp=timestamp,
        costs=costs,
    )

    return _handle_push(args, config, payload, "dashboard")


def _handle_import_usage(zip_path: str) -> int:
    """Import DeepSeek usage cost CSV from a zip file."""
    try:
        daily_costs, monthly_total, last_date = import_cost_csv(zip_path)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    usage = load_usage()
    seed_monthly_cost(usage, daily_costs, monthly_total, last_date)
    save_usage(usage)

    print(f"Imported {len(daily_costs)} days of cost data from {zip_path}")
    print(f"Month: {last_date[:7]}")
    print(f"Month-to-date total: ¥{monthly_total:,.2f}")
    print(f"Last date covered: {last_date}")
    print(f"Saved to data/usage_history.json")
    return 0


def _handle_push(
    args: argparse.Namespace,
    config,
    payload: dict,
    label: str,
) -> int:
    """Push payload to device or print in dry-run mode."""
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        logger.info("Dry-run: %s payload printed to stdout", label)
        return 0

    try:
        msg = push_canvas(config.dot_api_key, config.dot_device_id, payload)
        logger.info("Pushed %s to device: %s", label, msg)
        return 0
    except DotAuthError as e:
        logger.error("Dot auth error: %s", e)
        return 1
    except DotDeviceNotFoundError as e:
        logger.error("Device not found: %s", e)
        return 1
    except DotValidationError as e:
        logger.error("Canvas validation error: %s", e)
        return 1
    except DotPushError as e:
        logger.error("Dot push error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
