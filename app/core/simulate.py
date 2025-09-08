"""Simulation routines for compensation plans."""
from typing import Dict, Any

from . import composer


def run_simulation(plan_id: str, performance: Dict[str, float]) -> Dict[str, Any]:
    """Simulate payouts for reps under the plan.

    Uses the commission rate stored for the given ``plan_id``. If the plan
    is unknown, a default rate of 10%% is applied.
    """
    details = composer.PLAN_STORE.get(plan_id, {})
    rate = float(details.get("commission_rate", 0.1))
    payouts = {rep: round(rev * rate, 2) for rep, rev in performance.items()}
    total = round(sum(payouts.values()), 2)
    return {"plan_id": plan_id, "payouts": payouts, "total_payout": total}
