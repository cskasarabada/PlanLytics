"""Simulation routines for compensation plans."""
from typing import Dict, Any


def run_simulation(plan_id: str, performance: Dict[str, float]) -> Dict[str, Any]:
    """Simulate payouts for reps under the plan.

    Args:
        plan_id: Identifier of the plan to simulate.
        performance: Mapping of rep names to achieved revenue.

    Returns:
        A dictionary containing calculated payouts per rep and the total.
    """
    payouts = {rep: round(rev * 0.1, 2) for rep, rev in performance.items()}
    total = round(sum(payouts.values()), 2)
    return {"plan_id": plan_id, "payouts": payouts, "total_payout": total}

    # TODO: Incorporate plan-specific simulation logic.
