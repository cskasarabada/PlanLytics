# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Request, Response, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import shutil
import os
import time
import pandas as pd
from dataclasses import asdict
import hmac
import hashlib
import secrets
import redis.asyncio as redis

from ..core.ai_agents import DocumentAnalyzerAgent
from fastapi.exceptions import RequestValidationError


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

# ---------- Exception Handlers ----------
@app.exception_handler(Exception)
async def _unhandled(request, exc):
    print(f"[unhandled] {type(exc).__name__}: {exc}")
    return JSONResponse({"error": f"Server error: {type(exc).__name__}: {exc}"}, status_code=500)


@app.exception_handler(RequestValidationError)
async def _validation(request, exc):
    return JSONResponse({"error": "Invalid request body", "details": exc.errors()}, status_code=422)


# ---------- Helpers ----------
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".csv", ".log", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MAX_UPLOAD_MB = 50

SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me")
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def _sign_session(sid: str) -> str:
    sig = hmac.new(SESSION_SECRET.encode(), sid.encode(), hashlib.sha256).hexdigest()
    return f"{sid}.{sig}"


def _verify_session(cookie: str | None) -> str | None:
    if not cookie:
        return None
    try:
        sid, sig = cookie.split(".", 1)
        expected = hmac.new(SESSION_SECRET.encode(), sid.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected):
            return sid
    except Exception:
        return None
    return None


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

    # Writing Excel can fail if optional deps like openpyxl aren't installed.
    # Avoid crashing the API by catching any error and returning only CSV.
    xlsx_name = None
    try:
        df.to_excel(xlsx_path, index=False)
        xlsx_name = xlsx_path.name
    except Exception:
        pass

    return {"csv": csv_path.name, "xlsx": xlsx_name}


# ---------- Routes ----------
@app.get("/healthz")
def healthz():
    # light cleanup on health hits to keep /tmp tidy
    _clean_tmp(UPLOAD_DIR)
    _clean_tmp(OUTPUT_DIR)
    return {"ok": True}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    try:
        filename = _safe_name(file.filename)
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            return JSONResponse({"error": f"Unsupported file type: {ext}"}, status_code=400)

        # best-effort size guard
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
    except Exception as e:
        print(f"[upload] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"Upload failed: {e}"}, status_code=500)



@app.post("/api/analyze")
async def analyze(payload: dict):
    try:
        filename = _safe_name(str(payload.get("filename", "")))
        if not filename:
            return JSONResponse({"error": "filename required"}, status_code=400)

        src = UPLOAD_DIR / filename
        if not src.exists():
            print("[analyze] upload dir contents:", [p.name for p in UPLOAD_DIR.glob("*")])
            return JSONResponse({"error": f"File not found: {filename}"}, status_code=404)

        rows = extract_text(src)
        out = write_outputs(filename, rows)

        return {
            "message": "Analysis complete",
            "rows": len(rows),
            "download_url_csv": f"/api/download/{out['csv']}",
            "download_url_xlsx": f"/api/download/{out['xlsx']}",
        }
    except Exception as e:
        print(f"[analyze] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"Analyze failed: {e}"}, status_code=500)


@app.post("/api/agent")
async def agent_analysis(payload: dict):
    """Run advanced AI analysis using the DocumentAnalyzerAgent."""
    filename = _safe_name(str(payload.get("filename", "")))
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)

    src = UPLOAD_DIR / filename
    if not src.exists():
        return JSONResponse({"error": f"File not found: {filename}"}, status_code=404)

    rows = extract_text(src)
    text = "\n\n".join(r.get("content", "") for r in rows if r.get("content"))

    agent = DocumentAnalyzerAgent()
    result = await agent.execute({"text": text, "template": payload.get("template", "master")})

    return asdict(result)


@app.post("/api/homechat")
async def homechat(payload: dict, request: Request, response: Response):
    """Simple mini chat with per-visitor limits."""
    ip = request.client.host if request.client else ""
    sid = _verify_session(request.cookies.get("hc_sid"))
    if not sid:
        sid = secrets.token_hex(16)
        response.set_cookie(
            "hc_sid",
            _sign_session(sid),
            max_age=365 * 24 * 3600,
            httponly=True,
            samesite="lax",
        )

    date = time.strftime("%Y%m%d")
    key = f"homechat:{date}:{sid}:{ip}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, 24 * 3600)
        if count > 10:
            raise HTTPException(status_code=429, detail="Daily question limit reached")
        burst_key = f"homechat:burst:{sid}:{ip}"
        if not await redis_client.setnx(burst_key, 1):
            raise HTTPException(status_code=429, detail="Too many requests")
        await redis_client.expire(burst_key, 1)
    except Exception:
        count = 0

    question = str(payload.get("question", ""))
    answer = f"Echo: {question}"
    remaining = max(0, 10 - count)
    return {"answer": answer, "remaining": remaining}


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

@app.get("/api/diagnostics")
def diagnostics():
    return {
        "uploads": [p.name for p in UPLOAD_DIR.glob("*")],
        "outputs": [p.name for p in OUTPUT_DIR.glob("*")],
    }

# SPA fallback so client-side routes work (non-API/Static paths → index.html)
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    p = request.url.path
    if p.startswith("/api") or p.startswith("/static") or p in ("/docs", "/openapi.json", "/healthz"):
        return await call_next(request)
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return await call_next(request)
