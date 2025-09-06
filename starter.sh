#!/bin/bash
set -e

# Navigate to backend
cd "$(dirname "$0")/backend"

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Start FastAPI server
echo "Starting FastAPI server at http://localhost:8080 ..."
python -m uvicorn app:app --reload --port 8080
