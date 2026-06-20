"""Dot Canvas API client for pushing content to Quote/0 device."""

import json
import ssl
import urllib.request
import urllib.error
from typing import Any


class DotPushError(Exception):
    pass


class DotAuthError(DotPushError):
    pass


class DotDeviceNotFoundError(DotPushError):
    pass


class DotValidationError(DotPushError):
    pass


def push_canvas(api_key: str, device_id: str, payload: dict[str, Any]) -> str:
    """Push canvas content to a Quote/0 device.

    Args:
        api_key: Dot API bearer token.
        device_id: Device serial number.
        payload: Complete Canvas API request body (including windowData).

    Returns:
        The server response message string.

    Raises:
        DotAuthError: Invalid API key (401/403).
        DotDeviceNotFoundError: Device not found (404).
        DotValidationError: Invalid payload (400).
        DotPushError: Other push failures.
    """
    url = f"https://dot.mindreset.tech/api/authV2/open/device/{device_id}/canvas"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            status = resp.status
            resp_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        status = e.code
        resp_body = e.read().decode("utf-8") if e.fp else ""
    except urllib.error.URLError as e:
        raise DotPushError(f"Network error pushing to Dot Canvas API: {e}") from e

    if status in (200, 201):
        try:
            data = json.loads(resp_body)
            return data.get("message", "OK")
        except json.JSONDecodeError:
            return resp_body

    if status == 400:
        msg = _extract_message(resp_body)
        raise DotValidationError(f"Canvas API validation error: {msg}")
    if status in (401, 403):
        raise DotAuthError(
            f"Dot API authentication failed (HTTP {status}). "
            "Check your DOT_API_KEY."
        )
    if status == 404:
        raise DotDeviceNotFoundError(
            f"Device {device_id} not found (HTTP 404). "
            "Check DOT_DEVICE_ID and ensure Canvas API content is "
            "added to the device loop in Content Studio."
        )
    if 500 <= status < 600:
        msg = _extract_message(resp_body)
        raise DotPushError(f"Dot API server error (HTTP {status}): {msg}")

    raise DotPushError(f"Dot API unexpected response (HTTP {status}): {resp_body[:200]}")


def _extract_message(resp_body: str) -> str:
    """Extract error message from JSON response body."""
    try:
        data = json.loads(resp_body)
        return data.get("message", resp_body[:200])
    except json.JSONDecodeError:
        return resp_body[:200]
