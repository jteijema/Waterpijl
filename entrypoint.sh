#!/bin/sh

CRON_SCHEDULE="${CRON_SCHEDULE:-0 8,20 * * *}"

echo "=== Water Monitor Container Started ==="
echo "Current container time: $(date)"
echo "Setting up cron schedule: ${CRON_SCHEDULE}"
echo "${CRON_SCHEDULE} cd /app && /usr/local/bin/python src/main.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/crontabs/root
echo "Scanning for waterlevel ${ALERT_LEVEL} cm +NAP...."

# Hand over PID 1 to the command passed from the Dockerfile CMD
exec "$@"
