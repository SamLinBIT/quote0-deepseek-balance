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

# Check if any argument contains --dry-run
DRY_RUN=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]] && DRY_RUN=true
done

if $DRY_RUN; then
    # Dry-run: print directly to terminal
    "${SCRIPT_DIR}/.venv/bin/python" -m deepseek_balance.main "$@"
else
    # Normal run: log to file (for cron)
    mkdir -p logs
    "${SCRIPT_DIR}/.venv/bin/python" -m deepseek_balance.main "$@" >> "${SCRIPT_DIR}/logs/balance_cron.log" 2>&1
fi
