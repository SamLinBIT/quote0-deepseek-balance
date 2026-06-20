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
export TZ_OFFSET="${TZ_OFFSET:-8}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Bootstrap Python environment
PYTHON_BIN=""
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON_BIN="$VENV_PYTHON"
elif command -v uv &>/dev/null; then
    echo "[bootstrap] Creating venv with uv..."
    uv venv --quiet && PYTHON_BIN="$VENV_PYTHON"
elif command -v python3 &>/dev/null; then
    echo "[bootstrap] Creating venv with python3..."
    if python3 -m venv .venv 2>/dev/null; then
        PYTHON_BIN="$VENV_PYTHON"
    else
        echo "[bootstrap] venv unavailable (python3-venv not installed)"
        echo "[bootstrap] Falling back to system python3 (project has no deps)"
        PYTHON_BIN="$(command -v python3)"
    fi
else
    echo "[ERROR] python3 not found. Install Python 3.10+ first."
    exit 1
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
