FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc, libpq-dev for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import time, os; exit(0 if os.path.exists('/tmp/worker_heartbeat') and time.time() - os.path.getmtime('/tmp/worker_heartbeat') < 30 else 1)"

CMD ["python", "src/consumer.py"]
