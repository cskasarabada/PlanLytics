# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# System deps incl. Tesseract for pytesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libtesseract-dev curl gcc g++ \
 && rm -rf /var/lib/apt/lists/*

# Faster, reliable Python installs
COPY requirements.txt .
# let pip build pure-Python sdists like langdetect
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt

# App code
COPY . .

# Create dirs
RUN mkdir -p data/uploads data/outputs logs && chmod +x starter.sh || true

# Healthcheck path your app already exposes
ENV PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Start FastAPI
CMD ["uvicorn", "app_enhanced:app", "--host", "0.0.0.0", "--port", "8080"]
