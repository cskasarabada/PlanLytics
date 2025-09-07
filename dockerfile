
# ---------- Frontend build ----------
# FROM node:20-alpine AS frontend
# WORKDIR /app
# COPY frontend/ ./
# RUN npm ci || npm i
# RUN npm run build

FROM python:3.12-slim AS runtime
# ... (rest unchanged)
# COPY --from=frontend /app/../backend/static /app/static   # <- also comment or remove this

ENV PYTHONUNBUFFERED=1     PYTHONDONTWRITEBYTECODE=1     PORT=8080

# System deps (OCR optional - comment out if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends     tesseract-ocr libtesseract-dev curl gcc g++  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Backend requirements first for cache
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel --root-user-action=ignore  && pip install --no-cache-dir --prefer-binary -r /app/requirements.txt --root-user-action=ignore

# App code
COPY backend/ /app/
# Copy built frontend into static
COPY --from=frontend /app/../backend/static /app/static

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3   CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
