# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import os
import io
import pandas as pd

# Optional imports for richer extraction (they are in your env per your logs)
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

APP_ROOT = Path(__file__).resolve().parent.parent  # backend/
STATIC_DIR = APP_ROOT / "static"                   # backend/static
INDEX_FILE = STATIC_DIR / "index.html"

UPLOAD_DIR = Path("/tmp/uploads")
OUTPUT_DIR = Path("/tmp/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="PlanLytics", version="1.1.0")

# Serve static UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------- Helpers ----------

def _safe_name(name: str) -> str:
    # very light sanitization for filenames
    return os.path.basename(name).replace("..", "_")

def extract_text(file_path: Path) -> list[dict]:
    """
    Return a list of rows [{'section': str, 'content': str}] extracted from the file.
    - PDF: page-wise text
    - Image: OCR full text
    - TXT: full text
    - Fallback: read bytes length
    """
    name = file_path.name.lower()

    rows: list[dict] = []

    # PDF via PyMuPDF
    if name.endswith(".pdf") and fitz is not None:
        try:
            with fitz.open(file_path) as doc:
                for i, page in enumerate(doc, start=1):
                    txt = page.get_text() or ""
                    rows.append({"section": f"page_{i}", "content": txt.strip()})
            if rows:
                return rows
        except Exception as e:
            rows.append({"section": "error", "content": f"PDF parse error: {e}"})

    # Common image types → OCR
    if any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")) and Image and pytesseract:
        try:
            with Image.open(file_path) as im:
                text = pytesseract.image_to_string(im)
            rows.append({"section": "image_ocr", "content": text.strip()})
            return rows
        except Exception as e:
            rows.append({"section": "error", "content": f"OCR error: {e}"})

    # Plain text
    if any(name.endswith(ext) for ext in (".txt", ".md", ".csv", ".log")):
        try:
            text = file_path.read_text(errors="ignore")
            rows.append({"section": "text", "content": text.strip()})
            return rows
        except Exception as e:
            rows.append({"section": "error", "content": f"Text read error: {e}"})

    # Fallback: just report basic info
    try:
        size = file_path.stat().st_size
        rows.append({"section": "info", "content": f"Unsupported type. Bytes: {size}"})
    except Exception as e:
        rows.append({"section": "error", "content": f"Stat error: {e}"})
    return rows


def write_outputs(base_name: str, rows: list[dict]) -> dict:
    """
    Create CSV and Excel under /tmp/outputs with a consistent prefix.
    Returns dict with filenames.
    """
    safe = _safe_name(base_name)
    csv_name = f"analyzed_{safe}.csv"
    xlsx_name = f"analyzed_{safe}.xlsx"

    df = pd.DataFrame(rows) if rows else pd.DataFrame([{"section": "empty", "content": ""}])

    csv_path = OUTPUT_DIR / csv_name
    xlsx_path = OUTPUT_DIR / xlsx_name

    df.to_csv(csv_path, index=False)
    # Excel writer uses openpyxl in your env
    df.to_excel(xlsx_path, index=False)

    return {"csv": csv_path.name, "xlsx": xlsx_path.name}

# ---------- Routes ----------

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Save the uploaded file to /tmp/uploads."""
    filename = _safe_name(file.filename or "uploaded_file")
    target = UPLOAD_DIR / filename
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"filename": filename}

@app.post("/api/analyze")
async def analyze(payload: dict):
    """
    Analyze the previously-uploaded file and produce CSV+Excel.
    Expected body: {"filename": "<name>"}
    """
    filename = _safe_name(str(payload.get("filename", "")))
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)

    src = UPLOAD_DIR / filename
    if not src.exists():
        return JSONResponse({"error": f"File not found: {filename}"}, status_code=404)

    rows = extract_text(src)
    out = write_outputs(filename, rows)

    return {
        "message": "Analysis complete",
        "download_url_csv": f"/api/download/{out['csv']}",
        "download_url_xlsx": f"/api/download/{out['xlsx']}",
        "rows": len(rows),
    }

@app.get("/api/download/{filename}")
def download(filename: str):
    """Serve files from /tmp/outputs for download."""
    safe = _safe_name(filename)
    path = OUTPUT_DIR / safe
    if path.exists():
        return FileResponse(str(path), filename=safe)
    return JSONResponse({"error": "File not found"}, status_code=404)

# Serve index.html at root
@app.get("/", response_class=HTMLResponse)
async def root():
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return HTMLResponse("<h1>index.html not found in /static</h1>", status_code=404)

# SPA fallback for non-API routes
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    p = request.url.path
    if p.startswith("/api") or p.startswith("/static") or p in ("/docs", "/openapi.json", "/healthz"):
        return await call_next(request)
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return await call_next(request)
