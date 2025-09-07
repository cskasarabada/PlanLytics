
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
import os

app = FastAPI(title="PlanLytics Backend", version="1.0.0")

# CORS (adjust origins if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (frontend build output will be served from here)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health")
async def health():
    return {"ok": True, "version": "1.0.0"}

@app.get("/")
async def index():
    index_html = STATIC_DIR / "index.html"
    if index_html.exists():
        return HTMLResponse(index_html.read_text(encoding="utf-8"))
    # Fallback simple HTML if frontend not built yet
    return HTMLResponse(
        "<h1>PlanLytics</h1><p>Frontend build not found. Visit /health to test API.</p>",
        status_code=200,
    )

# Example upload endpoint (kept simple)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# NEW: request model for analyze
class AnalyzeRequest(BaseModel):
    filename: str

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """Run analysis on a previously uploaded file."""
    path = UPLOAD_DIR / req.filename
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {req.filename}")

    # TODO: replace this with your real analysis
    size = path.stat().st_size
    return {
        "filename": req.filename,
        "size": size,
        "message": "analysis placeholder",
        "notes": "Wire your processing here"
    }