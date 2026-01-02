"""Plan composition helpers."""
from typing import Dict, Any

from .constraints import validate_plan


# In-memory storage for generated plans. This allows other modules to
# access plan details by ``plan_id`` without a database.
PLAN_STORE: Dict[str, Dict[str, Any]] = {}


def suggest_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a basic plan suggestion.

    Args:
        params: Input parameters describing the desired plan. Supports
            ``sales_goal``, ``num_reps`` and optional ``commission_rate``.

    Returns:
        A dictionary with a generated ``plan_id`` and ``details``.
    """
    sales_goal = float(params.get("sales_goal", 0))
    reps = max(int(params.get("num_reps", 1)), 1)
    commission_rate = float(params.get("commission_rate", 0.1))
    quota_per_rep = sales_goal / reps if reps else 0
    details = {
        "quota_per_rep": quota_per_rep,
        "commission_rate": commission_rate,
        "num_reps": reps,
    }
    validate_plan(details)
    plan_id = f"plan_{reps}_{int(quota_per_rep)}"
    PLAN_STORE[plan_id] = details
    return {"plan_id": plan_id, "details": details}
