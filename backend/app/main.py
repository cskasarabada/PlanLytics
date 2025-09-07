from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import mimetypes

# --- Analysis imports
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from docx import Document  # python-docx

app = FastAPI(title="PlanLytics Backend", version="1.1.0")

# CORS (open; tighten later if you need)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR = STATIC_DIR / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Serve /static/*
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    return {"ok": True, "version": app.version}


@app.get("/")
async def index():
    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return HTMLResponse(index_html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>PlanLytics</h1><p>Frontend not found. Visit /health.</p>")


# -------- Upload --------
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    target = UPLOAD_DIR / file.filename
    with target.open("wb") as f:
        f.write(await file.read())
    return {"filename": file.filename, "size": target.stat().st_size}


# ======== Analysis helpers ========

def _ocr_pil(img: Image.Image) -> str:
    """OCR a PIL image with Tesseract (default language data installed is 'eng')."""
    try:
        return pytesseract.image_to_string(img)
    except Exception as e:
        return f"[OCR error: {e}]"

def _pdf_extract_with_ocr(pdf_path: Path) -> str:
    """Extract text from a PDF; OCR pages that have no text layer."""
    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text") or ""
            if text.strip():
                parts.append(text)
                continue
            # No text layer → rasterize & OCR
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            parts.append(_ocr_pil(img))
    return "\n".join(parts).strip()

def _image_ocr(img_path: Path) -> str:
    img = Image.open(img_path)
    return _ocr_pil(img).strip()

def _docx_text(docx_path: Path) -> str:
    doc = Document(docx_path)
    return "\n".join(p.text for p in doc.paragraphs).strip()

def _txt_text(txt_path: Path) -> str:
    return txt_path.read_text(encoding="utf-8", errors="ignore").strip()

def extract_text_generic(path: Path) -> str:
    """Route by extension/MIME and extract text, with OCR for PDFs/images."""
    ext = path.suffix.lower()

    if ext == ".pdf":
        return _pdf_extract_with_ocr(path)

    if ext in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        return _image_ocr(path)

    if ext == ".docx":
        return _docx_text(path)

    if ext in {".txt", ".md", ".csv"}:
        return _txt_text(path)

    mime, _ = mimetypes.guess_type(path.name)
    if mime and mime.startswith("image/"):
        return _image_ocr(path)

    raise HTTPException(status_code=415, detail=f"Unsupported file type: {path.suffix}")


# -------- Analyze --------
class AnalyzeRequest(BaseModel):
    filename: str  # name returned from /api/upload


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Extract text from a previously uploaded file.
    - PDFs: use text layer, OCR pages with no text.
    - Images: OCR.
    - TXT/CSV: read as text.
    - DOCX: extract paragraphs.
    Saves full text to /static/outputs/<stem>.txt and returns a preview + URL.
    """
    src = UPLOAD_DIR / req.filename
    if not src.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {req.filename}")

    text = extract_text_generic(src)

    out_name = f"{src.stem}.txt"
    out_path = OUTPUTS_DIR / out_name
    out_path.write_text(text or "", encoding="utf-8")

    return {
        "filename": req.filename,
        "bytes": src.stat().st_size,
        "chars": len(text),
        "preview": (text[:1000] + ("…" if len(text) > 1000 else "")),
        "output_url": f"/static/outputs/{out_name}",
        "note": "OCR applied where needed (Tesseract).",
    }
