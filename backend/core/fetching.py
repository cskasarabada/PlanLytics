"""
Fetch and extract text content from web URLs.
Handles HTML pages, hosted PDFs, Google Docs, and ChatGPT shared conversations.
"""
import re
import logging
import tempfile
import requests
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

from .parsing import extract_text

logger = logging.getLogger(__name__)


def fetch_url_text(url: str) -> Tuple[str, str]:
    """
    Fetch content from a URL and extract readable text.

    Returns:
        (extracted_text, source_type)
        source_type is one of: "html", "pdf", "google_doc", "chatgpt", "plain"
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    source_type = _classify_url(url)
    logger.info("Fetching URL [%s] classified as %s", url, source_type)

    if source_type == "google_doc":
        return _fetch_google_doc(url), source_type
    if source_type == "chatgpt":
        return _fetch_chatgpt_share(url), source_type
    if source_type == "pdf":
        return _fetch_pdf_url(url), source_type
    return _fetch_html_page(url), source_type


def _classify_url(url: str) -> str:
    """Classify a URL by its content source type."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if "docs.google.com" in host:
        return "google_doc"
    if "chatgpt.com" in host or "chat.openai.com" in host:
        return "chatgpt"
    if path.endswith(".pdf"):
        return "pdf"
    return "html"


# ── HTML helpers ──────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    """Convert HTML to plain text via regex (no BeautifulSoup needed)."""
    # Remove script and style blocks
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.I)
    # Block elements → newlines
    html = re.sub(r"<(br|p|div|h[1-6]|li|tr)[^>]*/?>", "\n", html, flags=re.I)
    # Strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Decode common entities
    for ent, ch in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&nbsp;", " "), ("&quot;", '"'), ("&#39;", "'")]:
        html = html.replace(ent, ch)
    # Collapse whitespace
    lines = [line.strip() for line in html.splitlines()]
    return "\n".join(line for line in lines if line)


# ── Source-specific fetchers ──────────────────────────────────

_HEADERS = {"User-Agent": "PlanLytics/1.0 (Compensation Plan Analyzer)"}


def _fetch_html_page(url: str) -> str:
    """Fetch an HTML page and extract readable text."""
    resp = requests.get(url, timeout=30, headers=_HEADERS)
    resp.raise_for_status()

    # If the server actually returned a PDF, handle that
    if "pdf" in resp.headers.get("content-type", "").lower():
        return _extract_pdf_bytes(resp.content)

    text = _html_to_text(resp.text)
    if not text.strip():
        raise ValueError("No readable text content found at URL")
    return text


def _fetch_google_doc(url: str) -> str:
    """
    Fetch a Google Doc via the /export?format=txt endpoint.
    Works for docs shared as 'Anyone with the link can view'.
    """
    match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Cannot extract Google Doc ID from: {url}")

    doc_id = match.group(1)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    resp = requests.get(export_url, timeout=30)
    resp.raise_for_status()

    text = resp.text.strip()
    if not text:
        raise ValueError("Google Doc is empty or not publicly accessible")
    return text


def _fetch_chatgpt_share(url: str) -> str:
    """
    Fetch a shared ChatGPT conversation page and extract text.
    Share URLs (chatgpt.com/share/...) render as HTML with conversation content.
    """
    resp = requests.get(url, timeout=30, headers=_HEADERS)
    resp.raise_for_status()

    text = _html_to_text(resp.text)
    if not text.strip():
        raise ValueError("No content found in ChatGPT shared conversation")
    return text


def _fetch_pdf_url(url: str) -> str:
    """Download a PDF from a URL and extract text."""
    resp = requests.get(url, timeout=60, headers=_HEADERS)
    resp.raise_for_status()
    return _extract_pdf_bytes(resp.content)


def _extract_pdf_bytes(pdf_bytes: bytes) -> str:
    """Write PDF bytes to a temp file, then use the existing parser."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        return extract_text(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
