# core/icm_review.py
"""
Simple in-memory store for ICM analysis review state.
Tracks analysis results between generation and deployment.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# In-memory store: analysis_id -> review state
_store: Dict[str, Dict[str, Any]] = {}


def save_review(
    analysis_id: str,
    analysis: dict,
    workbook_bytes: bytes,
    warnings: list,
    design_doc_bytes: bytes = None,
    config_doc_bytes: bytes = None,
) -> None:
    """Store analysis results for later review/download."""
    _store[analysis_id] = {
        "analysis": analysis,
        "workbook_bytes": workbook_bytes,
        "warnings": warnings,
        "status": "pending_review",
        "design_doc_bytes": design_doc_bytes,
        "config_doc_bytes": config_doc_bytes,
    }
    logger.info("Saved review state for %s", analysis_id)


def get_review(analysis_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve review state by analysis_id."""
    return _store.get(analysis_id)


def approve_review(analysis_id: str) -> bool:
    """Mark an analysis as approved for deployment."""
    review = _store.get(analysis_id)
    if not review:
        return False
    review["status"] = "approved"
    logger.info("Approved review %s", analysis_id)
    return True


def reject_review(analysis_id: str) -> bool:
    """Mark an analysis as rejected."""
    review = _store.get(analysis_id)
    if not review:
        return False
    review["status"] = "rejected"
    return True


def list_reviews() -> list:
    """List all review states."""
    return [
        {"analysis_id": aid, "status": r["status"], "warnings": r["warnings"]}
        for aid, r in _store.items()
    ]
