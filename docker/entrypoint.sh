#!/bin/sh
set -e

# ============================================================
# DeepSeek Balance Dashboard — Docker entrypoint
#
# 1. Load .env if present (fallback if --env-file not used)
# 2. Read config.json for timezone / schedule / import
# 3. Generate crontab and start crond
# ============================================================

CONFIG="/app/config.json"
CRONTAB="/etc/crontabs/root"
DATA_DIR="/app/data"
LOGS_DIR="/app/logs"

# --- Load .env secrets (only if user mounted it instead of --env-file) ---
if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
fi

# --- Create runtime directories ---
mkdir -p "$DATA_DIR" "$LOGS_DIR"

# --- Read config ---
if [ ! -f "$CONFIG" ]; then
    echo "[ERROR] $CONFIG not found. Mount your config.json to /app/config.json"
    exit 1
fi

# Timezone
TZ=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('timezone','Asia/Shanghai'))")
export TZ
echo "[entrypoint] Timezone: $TZ"

# --- Initial data import (DeepSeek usage ZIP) ---
IMPORT_ENABLED=$(python3 -c "import json; c=json.load(open('$CONFIG')); print('yes' if c.get('import',{}).get('enabled') else 'no')")
if [ "$IMPORT_ENABLED" = "yes" ]; then
    ZIP_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG'))['import']['zip_path'])")
    if [ -f "$ZIP_PATH" ]; then
        echo "[entrypoint] Importing usage data from $ZIP_PATH ..."
        python3 -m deepseek_balance.main --import-usage "$ZIP_PATH" >> "$LOGS_DIR/import.log" 2>&1 || true
    else
        echo "[entrypoint] WARN: import enabled but $ZIP_PATH not found — skipping"
    fi
fi

# --- Generate crontab from schedule ---
echo "[entrypoint] Generating crontab from $CONFIG ..."
python3 -c "
import json

config = json.load(open('$CONFIG'))
lines = []
for entry in config.get('schedule', []):
    cron = entry['cron']
    mode = entry.get('mode', 'dashboard')
    if mode == 'heatmap':
        flag = '--heatmap'
    elif mode == 'dashboard':
        flag = '--dashboard'
    else:
        flag = ''
    lines.append(f'{cron} cd /app && python3 -m deepseek_balance.main {flag} >> {LOGS_DIR}/balance_cron.log 2>&1')
# crond requires trailing newline
lines.append('')
open('$CRONTAB', 'w').write('\n'.join(lines))
print(f'[entrypoint] Wrote {len(lines)-1} cron jobs')
"

# --- Start cron in foreground, tail logs for docker logs ---
echo "[entrypoint] Starting crond ..."
crond -f -l 2 &
touch "$LOGS_DIR/balance_cron.log"
echo "[entrypoint] Container running. Watching logs ..."
tail -f "$LOGS_DIR/balance_cron.log"
