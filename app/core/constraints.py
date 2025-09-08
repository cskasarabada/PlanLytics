"""Stubbed constraint utilities for compensation plans."""
from typing import Dict, Any


def validate_plan(details: Dict[str, Any]) -> None:
    """Validate plan details against minimal constraints.

    Raises:
        ValueError: If a constraint is violated.
    """
    quota = details.get("quota_per_rep", 0)
    if quota <= 0:
        raise ValueError("Quota per rep must be positive")

    # TODO: Implement comprehensive constraint checks.
