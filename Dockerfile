FROM python:3.13-alpine

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Setup cron job (08:00 and 20:00 daily)
RUN echo "0 8,20 * * * cd /app && /usr/local/bin/python main.py > /proc/1/fd/1 2>/proc/1/fd/2" > /etc/crontabs/root

# Use the entrypoint script to handle startup logs
ENTRYPOINT ["/app/entrypoint.sh"]

# Run cron in foreground (this gets passed to the entrypoint as "$@" and becomes PID 1)
CMD ["crond", "-f", "-l", "2"]