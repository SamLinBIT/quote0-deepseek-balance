"""DeepSeek API client for fetching account balance."""

from __future__ import annotations

import json
import ssl
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass
class BalanceData:
    currency: str
    total_balance: Decimal
    granted_balance: Decimal
    topped_up_balance: Decimal
    is_available: bool
    fetched_at: datetime


class DeepSeekError(Exception):
    pass


class DeepSeekAuthError(DeepSeekError):
    pass


class DeepSeekNetworkError(DeepSeekError):
    pass


class DeepSeekParseError(DeepSeekError):
    pass


def fetch_balance(api_key: str) -> BalanceData:
    """Fetch DeepSeek account balance with retry logic.

    Raises:
        DeepSeekAuthError: Invalid API key (401/403)
        DeepSeekNetworkError: Network or server error (5xx, timeout)
        DeepSeekParseError: Invalid JSON response
    """
    url = "https://api.deepseek.com/user/balance"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    last_error: Exception | None = None

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = ssl.create_default_context()

            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")

            if status == 200:
                return _parse_response(body)

            if status in (401, 403):
                raise DeepSeekAuthError(
                    f"DeepSeek API returned HTTP {status}. "
                    "Check your DEEPSEEK_API_KEY."
                )

            if 500 <= status < 600:
                raise DeepSeekNetworkError(
                    f"DeepSeek API returned HTTP {status}: {body[:200]}"
                )

            # Unexpected 4xx
            raise DeepSeekNetworkError(
                f"DeepSeek API returned unexpected HTTP {status}: {body[:200]}"
            )

        except (DeepSeekAuthError, DeepSeekParseError):
            raise  # Don't retry auth or parse errors

        except (urllib.error.URLError, OSError, DeepSeekNetworkError) as e:
            last_error = e
            if attempt < 2:
                wait = 2 ** attempt  # 1s, 2s
                time.sleep(wait)
                continue
            raise DeepSeekNetworkError(
                f"Failed to fetch DeepSeek balance after 3 attempts: {e}"
            ) from e

    # Should not reach here, but type safety
    raise DeepSeekNetworkError(
        f"Failed to fetch DeepSeek balance: {last_error}"
    )


def _parse_response(body: str) -> BalanceData:
    """Parse DeepSeek balance API response."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise DeepSeekParseError(f"Invalid JSON from DeepSeek API: {e}") from e

    is_available = data.get("is_available", False)
    balance_infos = data.get("balance_infos", [])

    if not balance_infos:
        raise DeepSeekParseError(
            "DeepSeek API returned empty balance_infos array"
        )

    # Prefer CNY, fall back to first currency
    preferred = None
    for info in balance_infos:
        if info.get("currency") == "CNY":
            preferred = info
            break
    if preferred is None:
        preferred = balance_infos[0]

    def to_decimal(val: str | None) -> Decimal:
        if val is None:
            return Decimal("0")
        return Decimal(str(val))

    return BalanceData(
        currency=preferred.get("currency", "CNY"),
        total_balance=to_decimal(preferred.get("total_balance")),
        granted_balance=to_decimal(preferred.get("granted_balance")),
        topped_up_balance=to_decimal(preferred.get("topped_up_balance")),
        is_available=is_available,
        fetched_at=datetime.now(timezone.utc),
    )
