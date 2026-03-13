FROM python:3.13-alpine

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Use the entrypoint script to handle startup logs
ENTRYPOINT ["/app/entrypoint.sh"]

# Run cron in foreground (this gets passed to the entrypoint as "$@" and becomes PID 1)
CMD ["crond", "-f", "-l", "2"]