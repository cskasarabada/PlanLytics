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
    openapi_version="3.1.0",
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
ALLOWED_EXTS = {".pdf", ".txt", ".md", ".csv", ".log", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".docx", ".xlsx", ".xml"}
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


# ---------- ICM Pipeline Endpoints ----------
@app.post("/api/analyze-for-icm")
async def analyze_for_icm(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload a comp plan document and produce an ICM Optimizer-compatible workbook."""
    from ..core.pipeline import run_analysis_for_icm
    from ..core.icm_review import save_review

    try:
        filename = _safe_name(file.filename)
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            return JSONResponse({"error": f"Unsupported file type: {ext}"}, status_code=400)

        target = UPLOAD_DIR / filename
        with target.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # Parse optional params from query string
        org_id = int(request.query_params.get("org_id", "0"))
        template = request.query_params.get("template", "oracle_mapping")

        result = run_analysis_for_icm(target, template=template, org_id=org_id)

        # Save for review/download
        save_review(
            result["analysis_id"],
            result["analysis"],
            result["icm_workbook_bytes"],
            result["validation_warnings"],
            design_doc_bytes=result.get("design_doc_bytes"),
            config_doc_bytes=result.get("config_doc_bytes"),
        )

        # Save workbook + documents to disk for download
        aid = result["analysis_id"]
        wb_path = OUTPUT_DIR / f"icm_{aid}.xlsx"
        wb_path.write_bytes(result["icm_workbook_bytes"])
        if result.get("design_doc_bytes"):
            (OUTPUT_DIR / f"design_{aid}.docx").write_bytes(result["design_doc_bytes"])
        if result.get("config_doc_bytes"):
            (OUTPUT_DIR / f"config_{aid}.docx").write_bytes(result["config_doc_bytes"])
        if result.get("efficiency_doc_bytes"):
            (OUTPUT_DIR / f"efficiency_{aid}.docx").write_bytes(result["efficiency_doc_bytes"])
        if result.get("xml_export_bytes"):
            (OUTPUT_DIR / f"export_{aid}.xml").write_bytes(result["xml_export_bytes"])

        return {
            "analysis_id": aid,
            "message": "ICM analysis complete",
            "download_url": f"/api/icm-workbook/{aid}",
            "design_doc_url": f"/api/design-doc/{aid}",
            "config_doc_url": f"/api/config-doc/{aid}",
            "efficiency_doc_url": f"/api/efficiency-report/{aid}",
            "xml_export_url": f"/api/export-xml/{aid}",
            "efficiency_score": result.get("efficiency_report", {}).get("score"),
            "validation_warnings": result["validation_warnings"],
            "oracle_mapping_summary": {
                k: len(v) if isinstance(v, list) else v
                for k, v in result["analysis"].get("oracle_mapping", {}).items()
            },
        }
    except Exception as e:
        print(f"[analyze-for-icm] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"ICM analysis failed: {e}"}, status_code=500)


@app.post("/api/analyze-url")
async def analyze_url(payload: dict):
    """Analyze a compensation plan from a web URL (Google Doc, PDF link, wiki page)."""
    from ..core.pipeline import run_analysis_for_icm
    from ..core.icm_review import save_review
    from ..core.fetching import fetch_url_text

    url = payload.get("url", "").strip()
    if not url:
        return JSONResponse({"error": "url is required"}, status_code=400)

    org_id = int(payload.get("org_id", "0"))
    template = payload.get("template", "oracle_mapping")

    try:
        text, source_type = fetch_url_text(url)
    except ValueError as e:
        return JSONResponse({"error": f"Failed to fetch URL: {e}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"URL fetch error: {e}"}, status_code=502)

    try:
        result = run_analysis_for_icm(text=text, template=template, org_id=org_id)

        aid = result["analysis_id"]
        save_review(
            aid,
            result["analysis"],
            result["icm_workbook_bytes"],
            result["validation_warnings"],
            design_doc_bytes=result.get("design_doc_bytes"),
            config_doc_bytes=result.get("config_doc_bytes"),
        )

        wb_path = OUTPUT_DIR / f"icm_{aid}.xlsx"
        wb_path.write_bytes(result["icm_workbook_bytes"])
        if result.get("design_doc_bytes"):
            (OUTPUT_DIR / f"design_{aid}.docx").write_bytes(result["design_doc_bytes"])
        if result.get("config_doc_bytes"):
            (OUTPUT_DIR / f"config_{aid}.docx").write_bytes(result["config_doc_bytes"])
        if result.get("efficiency_doc_bytes"):
            (OUTPUT_DIR / f"efficiency_{aid}.docx").write_bytes(result["efficiency_doc_bytes"])
        if result.get("xml_export_bytes"):
            (OUTPUT_DIR / f"export_{aid}.xml").write_bytes(result["xml_export_bytes"])

        return {
            "analysis_id": aid,
            "message": "ICM analysis complete",
            "source_type": source_type,
            "source_url": url,
            "download_url": f"/api/icm-workbook/{aid}",
            "design_doc_url": f"/api/design-doc/{aid}",
            "config_doc_url": f"/api/config-doc/{aid}",
            "efficiency_doc_url": f"/api/efficiency-report/{aid}",
            "xml_export_url": f"/api/export-xml/{aid}",
            "efficiency_score": result.get("efficiency_report", {}).get("score"),
            "validation_warnings": result["validation_warnings"],
            "oracle_mapping_summary": {
                k: len(v) if isinstance(v, list) else v
                for k, v in result["analysis"].get("oracle_mapping", {}).items()
            },
        }
    except Exception as e:
        print(f"[analyze-url] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"ICM analysis failed: {e}"}, status_code=500)


@app.post("/api/analyze-text")
async def analyze_text(payload: dict):
    """Analyze a compensation plan from raw text or pasted ChatGPT output."""
    from ..core.pipeline import run_analysis_for_icm
    from ..core.icm_review import save_review

    text = payload.get("text", "").strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)

    org_id = int(payload.get("org_id", "0"))
    template = payload.get("template", "oracle_mapping")

    try:
        result = run_analysis_for_icm(text=text, template=template, org_id=org_id)

        aid = result["analysis_id"]
        save_review(
            aid,
            result["analysis"],
            result["icm_workbook_bytes"],
            result["validation_warnings"],
            design_doc_bytes=result.get("design_doc_bytes"),
            config_doc_bytes=result.get("config_doc_bytes"),
        )

        wb_path = OUTPUT_DIR / f"icm_{aid}.xlsx"
        wb_path.write_bytes(result["icm_workbook_bytes"])
        if result.get("design_doc_bytes"):
            (OUTPUT_DIR / f"design_{aid}.docx").write_bytes(result["design_doc_bytes"])
        if result.get("config_doc_bytes"):
            (OUTPUT_DIR / f"config_{aid}.docx").write_bytes(result["config_doc_bytes"])
        if result.get("efficiency_doc_bytes"):
            (OUTPUT_DIR / f"efficiency_{aid}.docx").write_bytes(result["efficiency_doc_bytes"])
        if result.get("xml_export_bytes"):
            (OUTPUT_DIR / f"export_{aid}.xml").write_bytes(result["xml_export_bytes"])

        return {
            "analysis_id": aid,
            "message": "ICM analysis complete",
            "source_type": "text",
            "download_url": f"/api/icm-workbook/{aid}",
            "design_doc_url": f"/api/design-doc/{aid}",
            "config_doc_url": f"/api/config-doc/{aid}",
            "efficiency_doc_url": f"/api/efficiency-report/{aid}",
            "xml_export_url": f"/api/export-xml/{aid}",
            "efficiency_score": result.get("efficiency_report", {}).get("score"),
            "validation_warnings": result["validation_warnings"],
            "oracle_mapping_summary": {
                k: len(v) if isinstance(v, list) else v
                for k, v in result["analysis"].get("oracle_mapping", {}).items()
            },
        }
    except Exception as e:
        print(f"[analyze-text] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"ICM analysis failed: {e}"}, status_code=500)


@app.post("/api/import-xml")
async def import_xml(
    request: Request,
    file: UploadFile = File(...),
):
    """Import Oracle ICM IcCnPlanCopy XML export directly into ICM workbook.

    Bypasses the AI/LLM pipeline entirely — structured XML parsing produces
    the oracle_mapping dict, then the existing transformer generates the workbook.
    """
    from ..core.pipeline import run_xml_import
    from ..core.icm_review import save_review

    try:
        filename = _safe_name(file.filename)
        ext = Path(filename).suffix.lower()
        if ext != ".xml":
            return JSONResponse({"error": "Only .xml files are accepted"}, status_code=400)

        target = UPLOAD_DIR / filename
        with target.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        # Parse optional params from query string
        org_id = int(request.query_params.get("org_id", "0"))
        plan_year_str = request.query_params.get("plan_year", "")
        plan_year = int(plan_year_str) if plan_year_str else None

        result = run_xml_import(target, plan_year=plan_year, org_id=org_id)

        aid = result["analysis_id"]
        save_review(
            aid,
            result["analysis"],
            result["icm_workbook_bytes"],
            result["validation_warnings"],
            design_doc_bytes=result.get("design_doc_bytes"),
            config_doc_bytes=result.get("config_doc_bytes"),
        )

        # Save workbook + documents to disk for download
        wb_path = OUTPUT_DIR / f"icm_{aid}.xlsx"
        wb_path.write_bytes(result["icm_workbook_bytes"])
        if result.get("design_doc_bytes"):
            (OUTPUT_DIR / f"design_{aid}.docx").write_bytes(result["design_doc_bytes"])
        if result.get("config_doc_bytes"):
            (OUTPUT_DIR / f"config_{aid}.docx").write_bytes(result["config_doc_bytes"])
        if result.get("efficiency_doc_bytes"):
            (OUTPUT_DIR / f"efficiency_{aid}.docx").write_bytes(result["efficiency_doc_bytes"])
        if result.get("xml_export_bytes"):
            (OUTPUT_DIR / f"export_{aid}.xml").write_bytes(result["xml_export_bytes"])

        # Extract source plan name from the analysis
        comp_plans = result["analysis"].get("oracle_mapping", {}).get("compensation_plans", [])
        source_plan_name = comp_plans[0]["name"] if comp_plans else "Unknown"

        return {
            "analysis_id": aid,
            "message": "XML import complete — workbook generated",
            "source_type": "xml_import",
            "source_plan_name": source_plan_name,
            "download_url": f"/api/icm-workbook/{aid}",
            "design_doc_url": f"/api/design-doc/{aid}",
            "config_doc_url": f"/api/config-doc/{aid}",
            "efficiency_doc_url": f"/api/efficiency-report/{aid}",
            "xml_export_url": f"/api/export-xml/{aid}",
            "efficiency_score": result.get("efficiency_report", {}).get("score"),
            "efficiency_findings": result.get("efficiency_report", {}).get("summary"),
            "validation_warnings": result["validation_warnings"],
            "oracle_mapping_summary": {
                k: len(v) if isinstance(v, list) else v
                for k, v in result["analysis"].get("oracle_mapping", {}).items()
            },
        }
    except Exception as e:
        print(f"[import-xml] ERROR: {type(e).__name__}: {e}")
        return JSONResponse({"error": f"XML import failed: {e}"}, status_code=500)


@app.get("/api/icm-workbook/{analysis_id}")
def get_icm_workbook(analysis_id: str):
    """Download the generated ICM workbook for review."""
    wb_path = OUTPUT_DIR / f"icm_{analysis_id}.xlsx"
    if wb_path.exists():
        return FileResponse(
            str(wb_path),
            filename=f"ICM_Config_{analysis_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return JSONResponse({"error": "Workbook not found"}, status_code=404)


@app.get("/api/design-doc/{analysis_id}")
def get_design_doc(analysis_id: str):
    """Download the generated Design Document for review."""
    doc_path = OUTPUT_DIR / f"design_{analysis_id}.docx"
    if doc_path.exists():
        return FileResponse(
            str(doc_path),
            filename=f"Design_Document_{analysis_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    return JSONResponse({"error": "Design document not found"}, status_code=404)


@app.get("/api/config-doc/{analysis_id}")
def get_config_doc(analysis_id: str):
    """Download the generated Configuration Document for review."""
    doc_path = OUTPUT_DIR / f"config_{analysis_id}.docx"
    if doc_path.exists():
        return FileResponse(
            str(doc_path),
            filename=f"Configuration_Document_{analysis_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    return JSONResponse({"error": "Configuration document not found"}, status_code=404)


@app.get("/api/efficiency-report/{analysis_id}")
def get_efficiency_report(analysis_id: str):
    """Download the Configuration Efficiency Report."""
    doc_path = OUTPUT_DIR / f"efficiency_{analysis_id}.docx"
    if doc_path.exists():
        return FileResponse(
            str(doc_path),
            filename=f"Efficiency_Report_{analysis_id}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    return JSONResponse({"error": "Efficiency report not found"}, status_code=404)


@app.get("/api/export-xml/{analysis_id}")
def get_export_xml(analysis_id: str):
    """Download the generated IcCnPlanCopy XML for Oracle ICM import."""
    xml_path = OUTPUT_DIR / f"export_{analysis_id}.xml"
    if xml_path.exists():
        return FileResponse(
            str(xml_path),
            filename=f"IcCnPlanCopy_{analysis_id}.xml",
            media_type="application/xml",
        )
    return JSONResponse({"error": "XML export not found"}, status_code=404)


@app.post("/api/icm-workbook/{analysis_id}/review")
async def review_icm_workbook(analysis_id: str, payload: dict):
    """Human review gate — approve or reject the generated config."""
    from ..core.icm_review import approve_review, reject_review, get_review

    review = get_review(analysis_id)
    if not review:
        return JSONResponse({"error": "Analysis not found"}, status_code=404)

    approved = payload.get("approved", False)
    if approved:
        approve_review(analysis_id)
        return {"status": "approved", "analysis_id": analysis_id}
    else:
        reject_review(analysis_id)
        return {"status": "rejected", "analysis_id": analysis_id}


@app.get("/api/deploy-preview/{analysis_id}")
def deploy_preview(analysis_id: str):
    """Preview what objects will be deployed (no API calls made)."""
    from ..core.icm_deployer import preview_deployment
    from ..core.icm_review import get_review

    wb_path = OUTPUT_DIR / f"icm_{analysis_id}.xlsx"
    if not wb_path.exists():
        review = get_review(analysis_id)
        if review and review.get("workbook_bytes"):
            wb_path.write_bytes(review["workbook_bytes"])
        else:
            return JSONResponse({"error": "Workbook not found"}, status_code=404)

    return preview_deployment(wb_path)


@app.post("/api/deploy-to-icm/{analysis_id}")
async def deploy_to_icm(analysis_id: str, payload: dict):
    """Deploy the reviewed ICM workbook to Oracle Fusion ICM.

    Supports two credential modes:
    - config_path: path to ICM Optimizer config.yaml
    - Direct credentials: base_url + username + password in payload

    Returns deployment results with a detailed request/response log.
    """
    from ..core.icm_review import get_review
    from ..core.icm_deployer import deploy_to_oracle_icm

    review = get_review(analysis_id)
    if not review:
        return JSONResponse({"error": "Analysis not found"}, status_code=404)

    if review["status"] != "approved":
        return JSONResponse(
            {"error": f"Analysis must be approved first. Current status: {review['status']}"},
            status_code=400,
        )

    dry_run = payload.get("dry_run", False)

    # Ensure workbook exists on disk
    wb_path = OUTPUT_DIR / f"icm_{analysis_id}.xlsx"
    if not wb_path.exists():
        wb_path.write_bytes(review["workbook_bytes"])

    # Build approval tag for audit trail
    approved_at = review.get("reviewed_at", "")
    approval_tag = f"Analysis {analysis_id} | Approved: {approved_at}"

    # Support both config file and direct credential modes
    config_path = payload.get("config_path", "")
    base_url = payload.get("base_url", "")
    username = payload.get("username", "")
    password = payload.get("password", "")

    selected_org_id = int(payload.get("org_id", 0))

    if base_url and username and password:
        result = deploy_to_oracle_icm(
            excel_path=wb_path,
            dry_run=dry_run,
            base_url=base_url,
            username=username,
            password=password,
            org_id=selected_org_id,
            approval_tag=approval_tag,
        )
    elif config_path:
        result = deploy_to_oracle_icm(
            excel_path=wb_path,
            config_path=Path(config_path),
            dry_run=dry_run,
            org_id=selected_org_id,
            approval_tag=approval_tag,
        )
    else:
        return JSONResponse(
            {"error": "Provide either config_path or base_url+username+password"},
            status_code=400,
        )

    # Save detailed log to disk for later retrieval
    import json as _json
    detailed_log = result.get("detailed_log")
    if detailed_log:
        log_path = OUTPUT_DIR / f"deploy_log_{analysis_id}.json"
        with open(log_path, "w") as f:
            _json.dump(detailed_log, f, indent=2, default=str)

    return {
        "analysis_id": analysis_id,
        "deployment": result,
    }


@app.get("/api/deploy-log/{analysis_id}")
def get_deploy_log(analysis_id: str):
    """Retrieve the detailed deployment log for a given analysis."""
    import json as _json
    log_path = OUTPUT_DIR / f"deploy_log_{analysis_id}.json"
    if log_path.exists():
        with open(log_path) as f:
            return _json.load(f)
    return JSONResponse({"error": "Deployment log not found"}, status_code=404)


@app.get("/api/configured-workbook/{analysis_id}")
def get_configured_workbook(analysis_id: str):
    """Download the post-deployment configured workbook with Oracle IDs."""
    wb_path = OUTPUT_DIR / f"icm_configured_{analysis_id}.xlsx"
    if wb_path.exists():
        return FileResponse(
            str(wb_path),
            filename=f"ICM_Configured_{analysis_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return JSONResponse({"error": "Configured workbook not found. Run deployment first."}, status_code=404)


@app.get("/api/icm-reviews")
def list_icm_reviews():
    """List all ICM analysis review states."""
    from ..core.icm_review import list_reviews
    return {"reviews": list_reviews()}


# ---------- ICM Deployment Wizard Endpoints ----------
_deploy_sessions: dict = {}


@app.post("/api/icm-deploy/upload-config")
async def icm_deploy_upload_config(file: UploadFile = File(...)):
    """Upload an ICM Optimizer config.txt and return a config_id."""
    import configparser, yaml, uuid
    config_id = str(uuid.uuid4())[:8]

    config_dir = OUTPUT_DIR / "icm_configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"config_{config_id}.txt"
    with config_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    cp = configparser.ConfigParser()
    cp.read(str(config_path))
    yaml_config = {section: dict(cp[section]) for section in cp.sections()}
    yaml_path = config_dir / f"config_{config_id}.yaml"
    with yaml_path.open("w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False)

    api_section = yaml_config.get("api", {})
    _deploy_sessions[config_id] = {
        "config_path": str(config_path),
        "yaml_path": str(yaml_path),
        "base_url": api_section.get("base_url", ""),
        "username": api_section.get("username", ""),
    }

    return {
        "config_id": config_id,
        "message": "Config uploaded",
        "base_url": api_section.get("base_url", ""),
        "username": api_section.get("username", ""),
        "sections": list(yaml_config.keys()),
    }


@app.post("/api/icm-deploy/validate-api")
async def icm_deploy_validate_api(payload: dict):
    """Test Oracle API credentials."""
    from ..icm_optimizer.utils.api_client import APIClient

    base_url = payload.get("base_url", "")
    username = payload.get("username", "")
    password = payload.get("password", "")
    if not all([base_url, username, password]):
        return JSONResponse({"success": False, "message": "base_url, username, and password required"}, status_code=400)

    try:
        client = APIClient(base_url=base_url, username=username, password=password)
        response, status_code = client.get("/incentiveCompensationPerformanceMeasures?limit=1")
        if status_code == 200:
            return {"success": True, "message": "API credentials validated"}
        return {"success": False, "message": f"API returned status {status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {e}"}


@app.post("/api/icm-deploy/validate-excel")
async def icm_deploy_validate_excel(payload: dict):
    """Validate that an Excel file exists and list its sheets."""
    excel_path = payload.get("excel_path", "")
    if not excel_path or not Path(excel_path).exists():
        return {"success": False, "message": f"File not found: {excel_path}"}
    try:
        xls = pd.ExcelFile(excel_path)
        return {"success": True, "message": "Excel validated", "sheets": xls.sheet_names}
    except Exception as e:
        return {"success": False, "message": f"Cannot read Excel: {e}"}


@app.post("/api/icm-deploy/list-orgs")
async def icm_deploy_list_orgs(payload: dict):
    """Query Oracle instance for available Business Units (OrgIds).

    Returns a list of {org_id, name} dicts the user can choose from.
    Tries multiple Oracle REST endpoints to discover BUs.
    """
    from ..icm_optimizer.utils.api_client import APIClient

    base_url = payload.get("base_url", "")
    username = payload.get("username", "")
    password = payload.get("password", "")
    if not all([base_url, username, password]):
        return JSONResponse(
            {"success": False, "message": "base_url, username, and password required"},
            status_code=400,
        )

    try:
        client = APIClient(base_url=base_url, username=username, password=password)
        orgs: list = []
        seen_ids: set = set()

        # Strategy 0: Query Business Units LOV directly (proper approach)
        response, status = client.get("/businessUnits?limit=500&fields=BusinessUnitId,BusinessUnitName,Status")
        if status == 200 and response.get("items"):
            for item in response["items"]:
                oid = item.get("BusinessUnitId", 0)
                name = item.get("BusinessUnitName", "")
                bu_status = item.get("Status", "")
                if oid and oid not in seen_ids:
                    seen_ids.add(oid)
                    status_label = f" [{bu_status}]" if bu_status else ""
                    orgs.append({"org_id": oid, "name": f"{name}{status_label}" if name else f"OrgId: {oid}"})

        # Strategy 1: Query compensation plans for distinct OrgId values (fallback)
        if not orgs:
            response, status = client.get("/compensationPlans?limit=100&fields=OrgId,Name")
            if status == 200 and response.get("items"):
                for item in response["items"]:
                    oid = item.get("OrgId", 0)
                    if oid and oid not in seen_ids:
                        seen_ids.add(oid)
                        orgs.append({"org_id": oid, "name": f"Business Unit (from plan: {item.get('Name', 'N/A')})"})

        # Strategy 2: Query performance measures if no plans found
        if not orgs:
            response, status = client.get("/incentiveCompensationPerformanceMeasures?limit=100&fields=OrgId,Name")
            if status == 200 and response.get("items"):
                for item in response["items"]:
                    oid = item.get("OrgId", 0)
                    if oid and oid not in seen_ids:
                        seen_ids.add(oid)
                        orgs.append({"org_id": oid, "name": f"Business Unit (from measure: {item.get('Name', 'N/A')})"})

        # Strategy 3: Query the workbook Config sheet if an analysis_id is provided
        analysis_id = payload.get("analysis_id", "")
        if analysis_id:
            wb_path = OUTPUT_DIR / f"icm_{analysis_id}.xlsx"
            if wb_path.exists():
                try:
                    cfg_df = pd.read_excel(wb_path, sheet_name="Config")
                    row = cfg_df.loc[cfg_df["Key"] == "OrgId"]
                    if not row.empty:
                        wb_org = int(row.iloc[0]["Value"])
                        if wb_org and wb_org not in seen_ids:
                            seen_ids.add(wb_org)
                            orgs.append({"org_id": wb_org, "name": "From ICM Workbook"})
                except Exception:
                    pass

        return {
            "success": True,
            "orgs": orgs,
            "message": f"Found {len(orgs)} business unit(s)" if orgs else "No business units found. Enter OrgId manually.",
        }
    except Exception as e:
        return {"success": False, "orgs": [], "message": f"Failed to query orgs: {e}"}


@app.post("/api/icm-deploy/run")
async def icm_deploy_run(payload: dict):
    """Run the 6-step ICM deployment.

    Supports two modes:
    - Config file mode: config_id + password
    - Direct credential mode: base_url + username + password (no config upload needed)
    """
    from ..core.icm_deployer import deploy_to_oracle_icm

    analysis_id = payload.get("analysis_id", "")
    config_id = payload.get("config_id", "")
    password = payload.get("password", "")
    base_url = payload.get("base_url", "")
    username = payload.get("username", "")
    selected_org_id = int(payload.get("org_id", 0))

    # Ensure workbook exists
    excel_path = OUTPUT_DIR / f"icm_{analysis_id}.xlsx"
    if not excel_path.exists():
        from ..core.icm_review import get_review
        review = get_review(analysis_id)
        if review and review.get("workbook_bytes"):
            excel_path.write_bytes(review["workbook_bytes"])
        else:
            return JSONResponse({"success": False, "message": f"Workbook not found for analysis {analysis_id}"}, status_code=404)

    # Direct credential mode (no config file needed)
    if base_url and username and password:
        result = deploy_to_oracle_icm(
            excel_path=excel_path,
            base_url=base_url,
            username=username,
            password=password,
            org_id=selected_org_id,
        )
    elif config_id:
        # Config file mode
        session = _deploy_sessions.get(config_id)
        if not session:
            return JSONResponse({"success": False, "message": "Provide credentials or upload config first."}, status_code=400)

        yaml_path = session["yaml_path"]

        if password:
            import yaml
            with open(yaml_path) as f:
                cfg = yaml.safe_load(f)
            cfg.setdefault("api", {})["password"] = password
            with open(yaml_path, "w") as f:
                yaml.dump(cfg, f, default_flow_style=False)

        result = deploy_to_oracle_icm(
            excel_path=excel_path,
            config_path=Path(yaml_path),
        )
    else:
        return JSONResponse({"success": False, "message": "Provide credentials or upload config first."}, status_code=400)

    # Save detailed log to disk for later retrieval / download
    import json as _json
    detailed_log = result.get("detailed_log")
    if detailed_log:
        log_path = OUTPUT_DIR / f"deploy_log_{analysis_id}.json"
        with open(log_path, "w") as f:
            _json.dump(detailed_log, f, indent=2, default=str)

    return {"analysis_id": analysis_id, "deployment": result}


# SPA fallback so client-side routes work (non-API/Static paths → index.html)
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    p = request.url.path
    if p.startswith("/api") or p.startswith("/static") or p in ("/docs", "/openapi.json", "/healthz"):
        return await call_next(request)
    # Serve .html files directly from static dir (e.g. /icm-e2e.html → static/icm-e2e.html)
    if p.endswith(".html"):
        static_file = STATIC_DIR / p.lstrip("/")
        if static_file.exists():
            return FileResponse(str(static_file))
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    return await call_next(request)
