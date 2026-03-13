#!/bin/sh

echo "=== Water Monitor Container Started ==="
echo "Current container time: $(date)"
echo "Loaded crontab for root:"
crontab -l
echo "Starting cron daemon..."
echo "Scanning for waterlevel ${THRESHOLD} cm +NAP...."

# Hand over PID 1 to the command passed from the Dockerfile CMD
exec "$@"
