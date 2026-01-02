"""Oracle ICM export helpers."""
from datetime import datetime
from typing import Dict, Any

from ..core import composer


def export_plan_to_icm(plan_id: str) -> Dict[str, Any]:
    """Return a structure representing an Oracle ICM export.

    In lieu of a real API integration this function assembles a payload with
    the stored plan details and a timestamp, which mirrors what an export
    operation might produce.
    """
    details = composer.PLAN_STORE.get(plan_id)
    if details is None:
        raise ValueError("Unknown plan_id")

    return {
        "plan_id": plan_id,
        "status": "exported",
        "system": "oracle_icm",
        "details": details,
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }
