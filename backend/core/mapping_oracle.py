# core/mapping_oracle.py
"""
Validate and enrich the oracle_mapping section of AI analysis output.
Ensures all 8 ICM object sections exist with sensible defaults.
"""
from datetime import datetime


def infer_oracle_objects(analysis_json: dict, org_id: int = 300000046987012) -> dict:
    """Validate and enrich oracle_mapping with defaults for missing fields."""
    om = analysis_json.setdefault("oracle_mapping", {})
    plan_year = datetime.now().year
    start_date = f"{plan_year}-01-01"
    end_date = f"{plan_year}-12-31"

    # Ensure all 8 ICM sections exist
    om.setdefault("compensation_plans", [])
    om.setdefault("plan_components", [])
    om.setdefault("rate_dimensions", [])
    om.setdefault("rate_tables", [])
    om.setdefault("rate_table_rates", [])
    om.setdefault("expressions", [])
    om.setdefault("performance_measures", [])
    om.setdefault("performance_goals", [])

    # Backfill org_id into objects that need it
    for section_key in (
        "compensation_plans", "plan_components", "rate_dimensions",
        "rate_tables", "performance_measures",
    ):
        for obj in om.get(section_key, []):
            obj.setdefault("org_id", org_id)

    # Backfill dates
    for section_key in ("compensation_plans", "plan_components", "performance_measures"):
        for obj in om.get(section_key, []):
            obj.setdefault("start_date", start_date)
            obj.setdefault("end_date", end_date)

    for pc in om.get("plan_components", []):
        pc.setdefault("rt_start_date", start_date)
        pc.setdefault("rt_end_date", end_date)

    # Auto-number expression sequences
    for i, expr in enumerate(om.get("expressions", []), start=1):
        expr.setdefault("sequence", i)
        expr.setdefault("expression_id", i)
        expr.setdefault("expression_detail_id", i)

    # Auto-number plan component calculation sequences
    for i, pc in enumerate(om.get("plan_components", []), start=1):
        pc.setdefault("calculation_sequence", i)

    # Backfill performance measure defaults
    for pm in om.get("performance_measures", []):
        pm.setdefault("process_transactions", "Yes")
        pm.setdefault("performance_interval", "Quarterly")
        pm.setdefault("active_flag", "Y")
        pm.setdefault("use_external_formula_flag", "N")
        pm.setdefault("running_total_flag", "N")
        pm.setdefault("f_year", plan_year)
        pm.setdefault("credit_category_name", "Sales Credit")

    return analysis_json
