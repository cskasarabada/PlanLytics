"""Constraint utilities for compensation plans."""
from typing import Dict, Any


def validate_plan(details: Dict[str, Any]) -> None:
    """Validate plan details against basic constraints.

    Raises:
        ValueError: If a constraint is violated.
    """
    quota = float(details.get("quota_per_rep", 0))
    if quota <= 0:
        raise ValueError("Quota per rep must be positive")

    rate = float(details.get("commission_rate", 0))
    if not (0 < rate <= 1):
        raise ValueError("Commission rate must be between 0 and 1")

    reps = int(details.get("num_reps", 1))
    if reps <= 0:
        raise ValueError("Number of reps must be positive")
