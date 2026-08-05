#!/usr/bin/env bash
# ============================================================
# DeepSeek Balance Dashboard — cron entry point
# Compatible with bash and zsh.
#
# Secrets are read from .env in the script directory.
# ============================================================

# --- Shell options (bash/zsh compatible) ----------------------------
# zsh uses 'pipe_fail' (with underscore), bash uses 'pipefail'.
if [[ -n "${ZSH_VERSION:-}" ]]; then
    set -euo pipe_fail
else
    set -euo pipefail
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load secrets --------------------------------------------------
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a            # auto-export all variables
    # shellcheck disable=SC1091
    . "${SCRIPT_DIR}/.env"
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
elif command -v uv >/dev/null 2>&1; then
    echo "[bootstrap] Creating venv with uv..."
    uv venv --quiet && PYTHON_BIN="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
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
mkdir -p logs
"$PYTHON_BIN" -m deepseek_balance.main "$@" 2>&1 | tee -a "${SCRIPT_DIR}/logs/balance_cron.log"
