# Dockerfile (root)

FROM python:3.12-slim

# Fast, predictable Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# --- Optional system deps (remove any you don't need) ---
# WeasyPrint needs cairo/pango; OCR needs tesseract.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 \
    fonts-liberation shared-mime-info \
    tesseract-ocr libtesseract-dev tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

# --- Python dependencies ---
# Use the ROOT requirements.txt (you removed backend/requirements.txt)
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel --root-user-action=ignore \
 && pip install --no-cache-dir --prefer-binary -r /app/requirements.txt --root-user-action=ignore

# --- App source ---
COPY . /app

# Optional: make sure Python can import from /app
ENV PYTHONPATH=/app

# Local dev convenience (Render sets $PORT in prod)
EXPOSE 8000

# --- Start the app ---
# Use shell form so ${PORT} expands at runtime. Default to 8000 locally.
CMD ["sh","-c","uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
