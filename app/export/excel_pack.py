"""Excel export helpers."""
from typing import Dict


def generate_workbook(plan_id: str) -> bytes:
    """Create a minimal workbook for the given plan.

    Returns raw ``.xlsx`` bytes. In real code this would leverage ``openpyxl``
    or ``xlsxwriter``.
    """
    # TODO: Replace with real Excel generation.
    content = f"Workbook for {plan_id}"
    return content.encode()
