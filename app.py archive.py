from __future__ import annotations

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from models.schemas import TemplateName
from core.pipeline import run_analysis
from core.exports import to_excel, to_pdf, simple_html_summary
from fastapi import FastAPI, File, UploadFile
import shutil


# -----------------------------
# Configuration
# -----------------------------
BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
UPLOADS = DATA_DIR / "uploads"
OUTPUTS = DATA_DIR / "outputs"
UPLOADS.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".docx", ".pdf", ".txt"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))  # configurable

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("app")

# -----------------------------
# App init + middleware
# -----------------------------
app = FastAPI(title="AI Compensation Automation – Local", version="0.2.0")

# CORS for local React dev server
App.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000", "http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated files (Excel/HTML/JSON) at /files
app.mount("/files", StaticFiles(directory=str(OUTPUTS)), name="files")


# -----------------------------
# Helpers
# -----------------------------
async def _save_upload(file: UploadFile, dest_dir: Path, job_id: str) -> Path:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    safe_name = Path(file.filename).name.replace(" ", "_")
    dest = dest_dir / f"{job_id}__{safe_name}"

    # stream to disk with size guard
    size = 0
    CHUNK = 1024 * 1024  # 1 MB
    with open(dest, "wb") as f:
        while True:
            chunk = await file.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                try:
                    dest.unlink(missing_ok=True)
                except Exception:
                    pass
                raise HTTPException(status_code=413, detail="File too large")
            f.write(chunk)
    await file.close()
    log.info("Saved upload %s (%s bytes)", dest.name, size)
    return dest


def _file_url(p: Path) -> str:
    return f"/files/{p.name}"


# -----------------------------
# Routes
# -----------------------------
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Redirect to Swagger UI for convenience."""
    return RedirectResponse(url="/docs")

app = FastAPI()

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"info": f"file saved at {file_location}"}


@app.get("/healthz", summary="Lightweight health check")
def healthz() -> dict:
    return {"status": "ok"}


UPLOAD_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>ICM Automation Analyzer</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body{font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 880px; margin: 2rem auto; padding: 0 1rem}
      .card{border:1px solid #e5e7eb; border-radius: 16px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.04)}
      .row{display:flex; gap:12px; align-items:center; flex-wrap:wrap}
      button{background:#111827;color:#fff;border:none;border-radius:12px;padding:10px 16px;cursor:pointer}
      button:disabled{opacity:.6; cursor:not-allowed}
      pre{background:#f8fafc; padding:12px; border-radius:12px; overflow:auto}
      a{color:#2563eb; text-decoration:none}
      a:hover{text-decoration:underline}
      label{font-weight:600}
      select,input[type=file]{padding:8px}
    </style>
  </head>
  <body>
    <h1>ICM Automation Analyzer</h1>
    <div class="card">
      <form id="f" class="row">
        <div><input type="file" name="file" required /></div>
        <div>
          <label for="template">Template:&nbsp;</label>
          <select name="template" id="template">
            <option value="master">Master Analysis</option>
            <option value="automation_framework">Automation Framework</option>
            <option value="vendor_checklist">Vendor Checklist</option>
            <option value="side_by_side">Side-by-Side Mapping</option>
            <option value="side_by_side_vendor_compare">Oracle vs SF Compare</option>
          </select>
        </div>
        <div><button id="btn">Analyze</button></div>
      </form>
    </div>

    <div id="out"></div>

    <script>
      const f = document.getElementById('f');
      const btn = document.getElementById('btn');
      const out = document.getElementById('out');

      f.onsubmit = async (e) => {
        e.preventDefault();
        btn.disabled = true; btn.textContent = 'Analyzing…';
        out.innerHTML = '';

        const fd = new FormData(f);
        try {
          const res = await fetch('/analyze', { method:'POST', body: fd });
          const data = await res.json();
          const pre = document.createElement('pre');
          pre.textContent = JSON.stringify(data, null, 2);

          const links = document.createElement('div');
          links.innerHTML = `
            <p><strong>Downloads:</strong>
              <ul>
                <li><a href="${data.excel_url}" target="_blank">Excel</a></li>
                <li><a href="${data.pdf_or_html_url}" target="_blank">PDF/HTML</a></li>
                <li><a href="${data.analysis_json_url}" target="_blank">JSON</a></li>
              </ul>
            </p>`;

          out.appendChild(links);
          out.appendChild(pre);
        } catch (err) {
          out.innerHTML = `<pre style="color:#b91c1c">${err}</pre>`
        } finally {
          btn.disabled = false; btn.textContent = 'Analyze';
        }
      }
    </script>
  </body>
</html>
"""


@app.get("/ui", include_in_schema=False)
def ui() -> HTMLResponse:
    return HTMLResponse(UPLOAD_HTML)


@app.post("/analyze", summary="Upload a plan document and run the automation analysis")
async def analyze(
    file: UploadFile = File(...),
    template: TemplateName = Form("master"),
) -> JSONResponse:
    # Generate a job id (stable for this request)
    job_id = uuid.uuid4().hex[:12]

    # Save the upload safely
    try:
        src_path = await _save_upload(file, UPLOADS, job_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        log.exception("Upload save failed")
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    # Run analysis pipeline
    try:
        analysis = run_analysis(src_path, template)
    except Exception as e:
        log.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    # Exports
    try:
        base_name = f"{job_id}__{Path(file.filename).name.replace(' ', '_')}"
        excel_path = OUTPUTS / f"{base_name}.xlsx"
        json_path = OUTPUTS / f"{base_name}.json"
        pdf_path = OUTPUTS / f"{base_name}.pdf"  # may be emitted as .html by to_pdf()

        to_excel(analysis, excel_path)
        (json_path).write_text(__import__("json").dumps(analysis, indent=2), encoding="utf-8")

        # HTML-as-PDF (avoids native deps if WeasyPrint not installed)
        html = simple_html_summary(analysis)
        to_pdf(html, pdf_path)

        resp = {
            "message": "ok",
            "template": str(template),
            "excel_url": _file_url(excel_path),
            "pdf_or_html_url": _file_url(pdf_path.with_suffix(".html")),
            "analysis_json_url": _file_url(json_path),
        }
        return JSONResponse(resp)
    except Exception as e:
        log.exception("Export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


# -----------------------------
# Error handlers (nice messages)
# -----------------------------
@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
