"""One-shot grayscale test for Quote/0 Canvas API.

Push 5 grayscale strips (div backgroundColor) to verify whether
the Canvas API server applies dithering to non-image elements.
Delete this file after testing.
"""

from __future__ import annotations

import os
import sys

# Allow importing from deepseek_balance without installing the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deepseek_balance.dot_push import (
    push_canvas,
    DotPushError,
    DotAuthError,
    DotDeviceNotFoundError,
    DotValidationError,
)


def _load_dotenv(dotenv_path: str = ".env") -> dict[str, str]:
    """Minimal .env parser — no dependency on config.py."""
    env: dict[str, str] = {}
    if not os.path.isfile(dotenv_path):
        print(f"[ERROR] .env not found at {dotenv_path}")
        sys.exit(1)
    with open(dotenv_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            env[k] = v
    return env


def build_test_payload() -> dict:
    """Build a simple Canvas payload: 5 grayscale strips side by side."""
    strips = [
        ("#ffffff", "白"),
        ("#cccccc", "浅灰"),
        ("#888888", "中灰"),
        ("#444444", "深灰"),
        ("#000000", "黑"),
    ]

    cells: list[dict] = []
    for color, label in strips:
        cells.append({
            "type": "div",
            "props": {
                "tw": "flex flex-col items-center justify-center w-[52px] h-full",
                "style": {
                    "backgroundColor": color,
                    "border": "1px solid #000000",
                },
                "children": [
                    {
                        "type": "span",
                        "props": {
                            "tw": "text-14-chillksans",
                            "style": {"color": "#ff0000" if color == "#000000" else "#000000"},
                            "children": label,
                        },
                    }
                ],
            },
        })

    return {
        "refreshNow": True,
        "taskAlias": "Grayscale Test",
        "border": 0,
        "layoutFull": {"tw": "p-[8px]"},
        "windowData": {
            "default": [
                {
                    "type": "div",
                    "props": {
                        "tw": "flex flex-col w-full h-full bg-white gap-[4px]",
                        "children": [
                            {
                                "type": "span",
                                "props": {
                                    "tw": "text-14-chillksans font-bold",
                                    "children": "灰阶测试: div backgroundColor",
                                },
                            },
                            {
                                "type": "div",
                                "props": {
                                    "tw": "flex flex-row flex-1 gap-[4px]",
                                    "children": cells,
                                },
                            },
                        ],
                    },
                }
            ]
        },
    }


def main() -> int:
    env = _load_dotenv()
    api_key = env.get("DOT_API_KEY", "")
    device_id = env.get("DOT_DEVICE_ID", "")

    if not api_key or not device_id:
        print("[ERROR] DOT_API_KEY or DOT_DEVICE_ID not set in .env")
        return 1

    payload = build_test_payload()

    try:
        msg = push_canvas(api_key, device_id, payload)
        print(f"✓ Pushed to device {device_id}: {msg}")
        print()
        print("→ Check the Quote/0 screen now.")
        print("  Can you distinguish all 5 grayscale levels?")
        print("  5 levels → use div backgroundColor for heatmap")
        print("  2 levels (only B/W) → need img-based approach with img-levels-8")
        print("  3 levels → reduce heatmap to 3 levels")
        return 0
    except DotAuthError as e:
        print(f"[ERROR] Auth failed: {e}")
        return 1
    except DotDeviceNotFoundError as e:
        print(f"[ERROR] Device not found: {e}")
        return 1
    except DotValidationError as e:
        print(f"[ERROR] Validation: {e}")
        return 1
    except DotPushError as e:
        print(f"[ERROR] Push failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
