# ---------- Backend image ----------
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# System deps (include Tesseract only if you need OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libtesseract-dev curl gcc g++ \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better caching
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel --root-user-action=ignore \
 && pip install --no-cache-dir --prefer-binary -r /app/requirements.txt --root-user-action=ignore

# Copy backend app code
COPY backend/ /app/

# If you don't build a frontend yet, app will serve a fallback page at "/"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
