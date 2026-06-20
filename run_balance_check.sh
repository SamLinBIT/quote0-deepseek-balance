#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# DeepSeek Balance Dashboard — cron entry point
#
# Set your real values below or export them before running.
# DO NOT commit this file if it contains real API keys.
#
# Usage:
#   ./run_balance_check.sh           # Full run
#   ./run_balance_check.sh --dry-run # Print payload only
# ============================================================

export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"
export DOT_API_KEY="${DOT_API_KEY:-}"
export DOT_DEVICE_ID="${DOT_DEVICE_ID:-}"
export INITIAL_RECHARGE="${INITIAL_RECHARGE:-}"
export CURRENCY="${CURRENCY:-CNY}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Bootstrap Python venv if missing
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
    if command -v uv &>/dev/null; then
        echo "[bootstrap] Creating venv with uv..."
        uv venv --quiet
    elif command -v python3 &>/dev/null; then
        echo "[bootstrap] Creating venv with python3..."
        python3 -m venv .venv
    else
        echo "[ERROR] Neither 'uv' nor 'python3' found. Install Python 3.10+ first."
        exit 1
    fi
fi

# Check if we should print to terminal (interactive commands)
INTERACTIVE=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" || "$arg" == "--import-usage" ]] && INTERACTIVE=true
done

if $INTERACTIVE; then
    # Interactive: print directly to terminal
    "$PYTHON_BIN" -m deepseek_balance.main "$@"
else
    # Cron: log to file
    mkdir -p logs
    "$PYTHON_BIN" -m deepseek_balance.main "$@" >> "${SCRIPT_DIR}/logs/balance_cron.log" 2>&1
fi
