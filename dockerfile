# Python 3.12 avoids the Pillow build break you hit on 3.13
FROM python:3.12-slim

# System deps for Tesseract OCR wrapper (pytesseract needs the binary)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr libtesseract-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Faster, safer installs
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    PIP_ONLY_BINARY=:all: pip install -r requirements.txt

# Bring in your app
COPY . .

# Start command (adjust to your entrypoint)
CMD ["python", "app.py"]
