# syntax=docker/dockerfile:1
FROM python:3.12-slim

# System deps (fast installs, no dev tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only reqs first for layer caching
COPY backend/requirements-lite.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code
COPY backend /app

# Env
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The platform (Render/Fly) usually injects $PORT
ENV PORT=8080

# Healthcheck (optional)
HEALTHCHECK --interval=30s --timeout=3s CMD curl -f http://localhost:$PORT/healthz || exit 1

# Start with production server (no reload)
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
