"""Configuration from environment variables."""

import os
import sys
from dataclasses import dataclass


@dataclass
class Config:
    deepseek_api_key: str
    dot_api_key: str
    dot_device_id: str
    initial_recharge: float | None
    currency: str  # "CNY" or "USD"


def load_config() -> Config:
    """Load and validate configuration from environment variables."""
    errors: list[str] = []

    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not deepseek_api_key:
        errors.append("DEEPSEEK_API_KEY is required")

    dot_api_key = os.environ.get("DOT_API_KEY", "").strip()
    if not dot_api_key:
        errors.append("DOT_API_KEY is required")

    dot_device_id = os.environ.get("DOT_DEVICE_ID", "").strip()
    if not dot_device_id:
        errors.append("DOT_DEVICE_ID is required")

    initial_recharge_str = os.environ.get("INITIAL_RECHARGE", "").strip()
    initial_recharge: float | None = None
    if initial_recharge_str:
        try:
            initial_recharge = float(initial_recharge_str)
            if initial_recharge < 0:
                errors.append("INITIAL_RECHARGE must be a non-negative number")
        except ValueError:
            errors.append(f"INITIAL_RECHARGE is not a valid number: {initial_recharge_str}")

    currency = os.environ.get("CURRENCY", "CNY").strip().upper()
    if currency not in ("CNY", "USD"):
        errors.append(f"CURRENCY must be CNY or USD, got: {currency}")

    if errors:
        for err in errors:
            print(f"[ERROR] {err}", file=sys.stderr)
        print("\nRequired environment variables:", file=sys.stderr)
        print("  DEEPSEEK_API_KEY  - DeepSeek API bearer token", file=sys.stderr)
        print("  DOT_API_KEY       - Dot Canvas API bearer token", file=sys.stderr)
        print("  DOT_DEVICE_ID     - Device serial number", file=sys.stderr)
        print("\nOptional:", file=sys.stderr)
        print("  INITIAL_RECHARGE  - Total amount ever recharged (for total spent calc)", file=sys.stderr)
        print("  CURRENCY          - Preferred currency: CNY (default) or USD", file=sys.stderr)
        sys.exit(1)

    return Config(
        deepseek_api_key=deepseek_api_key,
        dot_api_key=dot_api_key,
        dot_device_id=dot_device_id,
        initial_recharge=initial_recharge,
        currency=currency,
    )
