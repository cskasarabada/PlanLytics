# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import os
import time
import pandas as pd

# Optional parsers (the app runs even if these aren't available)
try:
    import fitz  # PyMuPDF for PDFs
except Exception:
    fitz = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

# ---------- Paths ----------
APP_ROOT = Path(__file__).resolve().parent.parent  # .../backend
STATIC_DIR = APP_ROOT / "static"                   # .../backend/static
INDEX_FILE = STATIC_DIR / "index.html"

UPLOAD_DIR = Path("/tmp/uploads")
OUTPUT_DIR = Path("/tmp/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- App ----------
app = FastAPI(
    title="PlanLytics — Incentive Planning & Pay",
    version="1.1.0",
    description="AI-assisted insights, risks & strategy — SI requirements and detailed setups.",
)

# Serve static assets (your landing page lives in backend/static/)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------- Helpers ----------
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".csv", ".log", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MAX_UPLOAD_MB = 50


def _safe_name(name: str) -> str:
    """Basic filename sanitization."""
    return os.path.basename(name or "").replace("..", "_") or "uploaded_file"


def _clean_tmp(dirpath: Path, max_age_sec: int = 24 * 3600) -> None:
    """Best-effort cleanup of old files in /tmp."""
    now = time.time()
    for p in dirpath.glob("*"):
        try:
            if p.is_file() and (now - p.stat().st_mtime) > max_age_sec:
                p.unlink()
        except Exception:
            pass


def extract_text(file_path: Path) -> list[dict]:
    """
    Produce a list of rows: [{'section': str, 'content': str}]
    - PDF (via PyMuPDF) → page-wise text
    - Images (via Tesseract) → OCR text
    - Plain text/CSV/MD/LOG → full text
    - Fallback → basic info
    """
    rows: list[dict] = []
    name = file_path.name.lower()

    # PDF
    if name.endswith(".pdf") and fitz is not None:
        try:
            with fitz.open(file_path) as doc:
                for i, page in enumerate(doc, start=1):
                    txt = page.get_text() or ""
                    rows.append({"section": f"page_{i}", "content": txt.strip()})
            return rows if rows else [{"section": "info", "content": "Empty PDF"}]
        except Exception as e:
            return [{"section": "error", "content": f"PDF parse error: {e}"}]

    # Images → OCR
    if any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")) and Image and pytesseract:
        try:
            with Image.open(file_path) as im:
                text = pytesseract.image_to_string(im)
            return [{"section": "image_ocr", "content": (text or "").strip()}]
        except Exception as e:
            return [{"section": "error", "content": f"OCR error: {e}"}]

    # Plain text-like
    if any(name.endswith(ext) for ext in (".txt", ".md", ".csv", ".log")):
        try:
            text = file_path.read_text(errors="ignore")
            return [{"section": "text", "content": (text or "").strip()}]
        except Exception as e:
            return [{"section": "error", "content": f"Text read error: {e}"}]

    # Fallback
    try:
        size = file_path.stat().st_size
        return [{"section": "info", "content": f"Unsupported type. Bytes: {size}"}]
    except Exception as e:
        return [{"section": "error", "content": f"Stat error: {e}"}]


def write_outputs(base_name: str, rows: list[dict]) -> dict:
    """Write CSV and XLSX under /tmp/outputs with 'analyzed_' prefix."""
    safe = _safe_name(base_name)
    csv_name = f"analyzed_{safe}.csv"
    xlsx_name = f"analyzed_{safe}.xlsx"

    df = pd.DataFrame(rows) if rows else pd.DataFrame([{"section": "empty", "content": ""}])

    csv_path = OUTPUT_DIR / csv_name
    xlsx_path = OUTPUT_DIR / xlsx_name

    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    return {"csv": csv_path.name, "xlsx": xlsx_path.name}


# ---------- Routes ----------
@app.get("/healthz")
def healthz():
    # light cleanup on health hits to keep /tmp tidy
    _clean_tmp(UPLOAD_DIR)
    _clean_tmp(OUTPUT_DIR)
    return {"ok": True}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    """
    Save the uploaded file to /tmp/uploads and return its server filename.
    Enforces basic extension and size checks.
    """
    filename = _safe_name(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        return JSONResponse({"error": f"Unsupported file type: {ext}"}, status_code=400)

    # Best-effort size check (uses header if present)
    try:
        cl = int(request.headers.get("content-length", "0"))
    except Exception:
        cl = 0
    if cl and cl > MAX_UPLOAD_MB * 1024 * 1024:
        return JSONResponse({"error": f"File too large (> {MAX_UPLOAD_MB} MB)"}, status_code=413)

    target = UPLOAD_DIR / filename
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"filename": filename}


@app.post("/api/analyze")
async def analyze(payload: dict):
    """
    Analyze a previously-uploaded file and produce CSV + Excel.
    Expected JSON body: {"filename": "<name>"}
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
        "rows": len(rows),
        "download_url_csv": f"/api/download/{out['csv']}",
        "download_url_xlsx": f"/api/download/{out['xlsx']}",
    }


@app.get("/api/download/{filename}")
def download(filename: str):
    """Serve analyzed files from /tmp/outputs."""
    safe = _safe_name(filename)
    path = OUTPUT_DIR / safe
    if path.exists():
        return FileResponse(str(path), filename=safe)
    return JSONResponse({"error": "File not found"}, status_code=404)


@app.get("/", response_class=HTMLResponse)
async def root():
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return HTMLResponse("<h1>index.html not found in /static</h1>", status_code=404)


# SPA fallback so client-side routes work (non-API/Static paths → index.html)
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    p = request.url.path
    if p.startswith("/api") or p.startswith("/static") or p in ("/docs", "/openapi.json", "/healthz"):
        return await call_next(request)
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return await call_next(request)
