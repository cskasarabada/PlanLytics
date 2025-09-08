"""Plan composition helpers."""
from typing import Dict, Any

from .constraints import validate_plan


def suggest_plan(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a stubbed plan suggestion.

    Args:
        params: Input parameters describing the desired plan.

    Returns:
        A dictionary with a generated ``plan_id`` and ``details``.
    """
    sales_goal = float(params.get("sales_goal", 0))
    reps = max(int(params.get("num_reps", 1)), 1)
    quota_per_rep = sales_goal / reps if reps else 0
    details = {"quota_per_rep": quota_per_rep}
    validate_plan(details)
    plan_id = f"plan_{reps}_{int(quota_per_rep)}"
    return {"plan_id": plan_id, "details": details}

    # TODO: Replace with real plan composition logic.
