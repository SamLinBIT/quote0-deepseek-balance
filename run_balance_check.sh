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

# Check if we should print to terminal (interactive commands)
INTERACTIVE=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" || "$arg" == "--import-usage" ]] && INTERACTIVE=true
done

if $INTERACTIVE; then
    # Interactive: print directly to terminal
    "${SCRIPT_DIR}/.venv/bin/python" -m deepseek_balance.main "$@"
else
    # Cron: log to file
    mkdir -p logs
    "${SCRIPT_DIR}/.venv/bin/python" -m deepseek_balance.main "$@" >> "${SCRIPT_DIR}/logs/balance_cron.log" 2>&1
fi
