"""Optimization utilities for compensation plans."""
from typing import Dict, Any

from . import composer


def optimize_plan(plan_id: str, objectives: Dict[str, float]) -> Dict[str, Any]:
    """Adjust plan parameters based on objectives.

    Currently supports a ``target_rate`` which updates the commission rate
    stored for the plan. The rate is clamped between 0 and 1.
    """
    details = composer.PLAN_STORE.get(plan_id)
    if details is None:
        raise ValueError("Unknown plan_id")

    target_rate = float(objectives.get("target_rate", details.get("commission_rate", 0.1)))
    target_rate = max(0.0, min(target_rate, 1.0))
    details["commission_rate"] = target_rate
    composer.PLAN_STORE[plan_id] = details
    return {"plan_id": plan_id, "plan": details}
