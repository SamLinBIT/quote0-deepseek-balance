#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# DeepSeek Balance Dashboard — cron entry point
#
# Secrets are read from .env in the script directory.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load secrets --------------------------------------------------
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a            # auto-export all variables
    source "${SCRIPT_DIR}/.env"
    set +a
else
    echo "[ERROR] .env file not found at ${SCRIPT_DIR}/.env"
    exit 1
fi

# --- Timezone (all Python time calls use this) ----------------------
export TZ='Asia/Shanghai'

# --- Apply defaults for optional vars ------------------------------
export CURRENCY="${CURRENCY:-CNY}"
export INITIAL_RECHARGE="${INITIAL_RECHARGE:-}"

# --- PATH (cron runs with minimal PATH) ----------------------------
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# --- Bootstrap Python environment ----------------------------------
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

# --- Run -----------------------------------------------------------
INTERACTIVE=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" || "$arg" == "--import-usage" ]] && INTERACTIVE=true
done

if $INTERACTIVE; then
    "$PYTHON_BIN" -m deepseek_balance.main "$@"
else
    mkdir -p logs
    "$PYTHON_BIN" -m deepseek_balance.main "$@" >> "${SCRIPT_DIR}/logs/balance_cron.log" 2>&1
fi
