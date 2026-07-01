FROM python:3.10-alpine

# cron is built into Alpine (busybox crond)
# tzdata provides timezone definitions
RUN apk add --no-cache tzdata

WORKDIR /app

# Copy application code (zero external dependencies)
COPY deepseek_balance/ ./deepseek_balance/

# Copy default config and entrypoint
COPY config.json ./
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Volumes for persistent data and optional .env mount
VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["/entrypoint.sh"]
