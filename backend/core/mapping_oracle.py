# core/mapping_oracle.py
"""
Validate and enrich the oracle_mapping section of AI analysis output.
Ensures all 11 ICM object sections exist with sensible defaults.

Object hierarchy (deployment order):
  Credit Categories → Rate Dimensions → Rate Tables → Expressions →
  Performance Measures → Plan Components → Compensation Plans →
  Performance Goals → Scorecards → Calculation Settings
"""
from datetime import datetime


def infer_oracle_objects(
    analysis_json: dict,
    org_id: int = 0,
    plan_year: int = None,
) -> dict:
    """Validate and enrich oracle_mapping with defaults for missing fields."""
    om = analysis_json.setdefault("oracle_mapping", {})
    # Track whether plan_year was explicitly provided by the caller
    explicit_plan_year = plan_year is not None
    if plan_year is None:
        plan_year = datetime.now().year
    start_date = f"{plan_year}-01-01"
    end_date = f"{plan_year}-12-31"

    # Ensure all 11 ICM sections exist
    om.setdefault("credit_categories", [])
    om.setdefault("compensation_plans", [])
    om.setdefault("plan_components", [])
    om.setdefault("rate_dimensions", [])
    om.setdefault("rate_tables", [])
    om.setdefault("rate_table_rates", [])
    om.setdefault("expressions", [])
    om.setdefault("performance_measures", [])
    om.setdefault("performance_goals", [])
    om.setdefault("scorecards", [])
    om.setdefault("calculation_settings", [])

    # Backfill org_id into objects that need it
    for section_key in (
        "compensation_plans", "plan_components", "rate_dimensions",
        "rate_tables", "performance_measures", "credit_categories",
    ):
        for obj in om.get(section_key, []):
            obj.setdefault("org_id", org_id)

    # Backfill dates — force-override when plan_year was explicitly provided
    for section_key in ("compensation_plans", "plan_components", "performance_measures"):
        for obj in om.get(section_key, []):
            if explicit_plan_year:
                obj["start_date"] = start_date
                obj["end_date"] = end_date
            else:
                obj.setdefault("start_date", start_date)
                obj.setdefault("end_date", end_date)

    for pc in om.get("plan_components", []):
        if explicit_plan_year:
            pc["rt_start_date"] = start_date
            pc["rt_end_date"] = end_date
        else:
            pc.setdefault("rt_start_date", start_date)
            pc.setdefault("rt_end_date", end_date)

    # Auto-number expression sequences
    for i, expr in enumerate(om.get("expressions", []), start=1):
        expr.setdefault("sequence", i)
        expr.setdefault("expression_id", i)
        expr.setdefault("expression_detail_id", i)
        expr.setdefault("expression_category", "Earnings")

    # Auto-number plan component calculation sequences + advanced defaults
    for i, pc in enumerate(om.get("plan_components", []), start=1):
        pc.setdefault("calculation_sequence", i)
        pc.setdefault("calculate_incentive", "Per interval")
        pc.setdefault("payout_frequency", "Period")
        pc.setdefault("split_attainment", "No")
        pc.setdefault("fixed_within_tier", "No")
        pc.setdefault("true_up", "No")
        pc.setdefault("include_indirect_credits", "None")

    # Backfill performance measure defaults
    # Use Oracle API codes directly (CN_PROCESS_TXN lookup: GROUP / INDIVIDUAL)
    for pm in om.get("performance_measures", []):
        pm.setdefault("process_transactions", "GROUP")
        pm.setdefault("performance_interval", "-1001")  # Quarterly
        pm.setdefault("active_flag", "Y")
        pm.setdefault("use_external_formula_flag", "N")
        pm.setdefault("running_total_flag", "N")
        if explicit_plan_year:
            pm["f_year"] = plan_year
        else:
            pm.setdefault("f_year", plan_year)
        pm.setdefault("credit_category_name", "Sales Credit")

    # Credit category action defaults.
    # "reuse" = exists in Oracle (deployer will look up, not create)
    # "create" = new category to create
    # "create_with_mapping" = new category + needs data migration mapping rules
    for cc in om.get("credit_categories", []):
        cc.setdefault("action", "reuse")

    # Backfill calculation settings defaults
    for cs in om.get("calculation_settings", []):
        cs.setdefault("calculate_incentive", "Per interval")
        cs.setdefault("process_transactions", "Grouped by interval")
        cs.setdefault("payout_frequency", "Period")
        cs.setdefault("split_attainment", "No")
        cs.setdefault("fixed_within_tier", "No")
        cs.setdefault("true_up", "No")
        cs.setdefault("include_indirect_credits", "None")
        cs.setdefault("running_total", "No")

    return analysis_json
