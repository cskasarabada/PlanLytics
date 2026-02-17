# core/icm_transformer.py
"""
Transforms PlanLytics AI analysis JSON into an ICM Optimizer-compatible
Excel workbook with 12 worksheets covering the full Oracle ICM object hierarchy.

Sheets (deployment order):
  1. Credit Categories    — credit category definitions
  2. Rate Dimension       — tier ranges for rate lookups
  3. Rate Table           — rate table containers
  4. Rate Table Rates     — individual rate values per tier
  5. Expression           — calculation formulas (attainment, earnings, rate input, weighted)
  6. Performance Measure  — what gets measured, with optional scorecard
  7. Plan Components      — links plans → measures → rates → formulas + calc settings
  8. Compensation Plans   — top-level plan containers
  9. Performance Goals    — targets per measure
 10. Scorecards           — scorecard rate table mappings (measure → score)
 11. Calculation Settings — advanced per-component settings (true-up, split, payout)
 12. Config               — workbook metadata
"""
import pandas as pd
from io import BytesIO
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Exact column names per sheet — must match PlanData.py / ICM Optimizer expectations
SHEET_COLUMNS = {
    "Credit Categories": [
        "CreditCategoryName", "Description", "OrgId", "Action",
    ],
    "Rate Dimension": [
        "Rate Dimension Name", "Rate Dimension Type", "Org ID",
        "Tier Sequence", "Minimum Amount", "Maximum Amount",
    ],
    "Rate Table": [
        "Rate Table Name", "Rate Table Type", "Org ID", "Display Name",
        "Rate Dimension Name",
    ],
    "Rate Table Rates": [
        "Rate Table Name", "Minimum Amount", "Maximum Amount",
        "Rate Value", "TierSequence",
    ],
    "Expression": [
        "Expression Name", "Expression ID", "Expression Detail Type",
        "Description", "Expression Type", "ExpressionCategory", "Sequence",
        "Measure Name", "Basic Attributes Group", "Basic Attribute Name",
        "Measure Result Attribute", "Plan Component Name",
        "Plan Component Result Attribute", "Constant Value",
        "Expression Operator", "Expression Detail ID",
    ],
    "Performance Measure": [
        "Name", "Description", "UnitOfMeasure", "OrgId", "StartDate",
        "EndDate", "MeasureFormulaExpressionName", "ProcessTransactions",
        "PerformanceInterval", "ActiveFlag", "UseExternalFormulaFlag",
        "RunningTotalFlag", "FYear", "CreditCategoryName",
        "ScorecardRateTableName",
    ],
    "Plan Components": [
        "PlanName", "Plan Component Name", "IncentiveType", "StartDate",
        "EndDate", "CalculationMethod", "OrgId", "Performance Measure Name",
        "Rate Table Name", "RTStartDate", "RTEndDate",
        "Incentive Formula Expression", "PerformanceMeasureWeight",
        "CalculationSequence", "EarningBasis",
        "CalculateIncentive", "Calculation Phase", "Earning Type",
        "PayoutFrequency",
        "SplitAttainment", "FixedWithinTier",
        "TrueUp", "TrueUpResetInterval",
        "IncludeIndirectCredits",
        "RateDimensionInputExpression",
    ],
    "Compensation Plans": [
        "Name", "StartDate", "EndDate", "Status", "Description",
        "DisplayName", "TargetIncentive", "OrgId", "Plan Component Name",
    ],
    "Performance Goals": [
        "PerformanceMeasureName", "GoalInterval", "GoalTarget",
    ],
    "Scorecards": [
        "ScorecardName", "PerformanceMeasureName", "RateTableName",
        "InputExpressionName", "Description",
    ],
    "Calculation Settings": [
        "PlanComponentName", "CalculateIncentive", "ProcessTransactions",
        "PayoutFrequency", "SplitAttainment", "FixedWithinTier",
        "TrueUp", "TrueUpResetInterval",
        "IncludeIndirectCredits", "RunningTotal",
    ],
    "Config": [
        "Key", "Value",
    ],
}


def transform_analysis_to_icm_workbook(
    analysis_json: Dict[str, Any],
    org_id: int = 0,
    plan_year: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Transform PlanLytics AI analysis output into DataFrames matching
    ICM Optimizer worksheet format.

    Args:
        analysis_json: The oracle_mapping section from AI analysis
        org_id: Oracle organization ID
        plan_year: Plan fiscal year (defaults to current year)

    Returns:
        Dict mapping sheet names to pandas DataFrames
    """
    if plan_year is None:
        plan_year = datetime.now().year

    oracle_data = analysis_json.get("oracle_mapping", analysis_json)
    start_date = f"{plan_year}-01-01"
    end_date = f"{plan_year}-12-31"

    # Apply year suffixes to avoid collision with prior-year Oracle objects.
    # Credit categories are NOT suffixed — they are reused across years.
    oracle_data = _apply_year_suffixes(oracle_data, plan_year)

    sheets = {}
    sheets["Credit Categories"] = _build_credit_categories(oracle_data, org_id)
    sheets["Rate Dimension"] = _build_rate_dimensions(oracle_data, org_id)
    sheets["Rate Table"] = _build_rate_tables(oracle_data, org_id)
    sheets["Rate Table Rates"] = _build_rate_table_rates(oracle_data)
    sheets["Expression"] = _build_expressions(oracle_data)
    sheets["Performance Measure"] = _build_performance_measures(
        oracle_data, org_id, plan_year, start_date, end_date
    )
    sheets["Plan Components"] = _build_plan_components(
        oracle_data, org_id, start_date, end_date
    )
    sheets["Compensation Plans"] = _build_compensation_plans(
        oracle_data, org_id, start_date, end_date
    )
    sheets["Performance Goals"] = _build_performance_goals(oracle_data)
    sheets["Scorecards"] = _build_scorecards(oracle_data)
    sheets["Calculation Settings"] = _build_calculation_settings(oracle_data)
    sheets["Config"] = _build_config(org_id, plan_year)

    return sheets


def write_icm_workbook(
    sheets: Dict[str, pd.DataFrame],
    output_path: Optional[Path] = None,
) -> bytes:
    """
    Write DataFrames to an Excel workbook matching ICM Optimizer format.

    Returns:
        bytes of the Excel workbook
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        # Format OrgId columns to avoid scientific notation
        workbook = writer.book
        org_id_sheets = [
            "Compensation Plans", "Plan Components",
            "Rate Dimension", "Performance Measure",
        ]
        for sn in org_id_sheets:
            if sn not in writer.sheets:
                continue
            ws = writer.sheets[sn]
            header_row = next(ws.rows)
            col_idx = None
            for i, cell in enumerate(header_row):
                if cell.value in ("OrgId", "Org ID"):
                    col_idx = i
                    break
            if col_idx is not None:
                for row in ws.iter_rows(
                    min_row=2, min_col=col_idx + 1, max_col=col_idx + 1
                ):
                    for cell in row:
                        cell.number_format = "0"

    workbook_bytes = buffer.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(workbook_bytes)
        logger.info("ICM workbook written to %s", output_path)

    return workbook_bytes


def validate_cross_references(sheets: Dict[str, pd.DataFrame]) -> List[str]:
    """Validate that names referenced across sheets are consistent."""
    warnings: List[str] = []

    plan_names = set()
    rt_names = set()
    pm_names = set()
    expr_names = set()
    cc_names = set()
    pc_names = set()

    if not sheets["Compensation Plans"].empty:
        plan_names = set(sheets["Compensation Plans"]["Name"].dropna())
    if not sheets["Rate Table"].empty:
        rt_names = set(sheets["Rate Table"]["Rate Table Name"].dropna())
    if not sheets["Performance Measure"].empty:
        pm_names = set(sheets["Performance Measure"]["Name"].dropna())
    if not sheets["Expression"].empty:
        expr_names = set(sheets["Expression"]["Expression Name"].dropna())
    if not sheets["Credit Categories"].empty:
        cc_names = set(sheets["Credit Categories"]["CreditCategoryName"].dropna())
    if not sheets["Plan Components"].empty:
        pc_names = set(sheets["Plan Components"]["Plan Component Name"].dropna())

    # Plan Components → Compensation Plans
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["PlanName"].dropna())
        missing = refs - plan_names
        if missing:
            warnings.append(f"Plan Components reference missing plans: {missing}")

    # Plan Components → Rate Tables
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["Rate Table Name"].dropna()) - {""}
        missing = refs - rt_names
        if missing:
            warnings.append(f"Plan Components reference missing rate tables: {missing}")

    # Plan Components → Performance Measures
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["Performance Measure Name"].dropna()) - {""}
        missing = refs - pm_names
        if missing:
            warnings.append(f"Plan Components reference missing measures: {missing}")

    # Rate Table Rates → Rate Tables
    if not sheets["Rate Table Rates"].empty:
        refs = set(sheets["Rate Table Rates"]["Rate Table Name"].dropna())
        missing = refs - rt_names
        if missing:
            warnings.append(f"Rate Table Rates reference missing tables: {missing}")

    # Performance Goals → Performance Measures
    if not sheets["Performance Goals"].empty:
        refs = set(sheets["Performance Goals"]["PerformanceMeasureName"].dropna())
        missing = refs - pm_names
        if missing:
            warnings.append(f"Performance Goals reference missing measures: {missing}")

    # Scorecards → Performance Measures + Rate Tables
    if not sheets["Scorecards"].empty:
        pm_refs = set(sheets["Scorecards"]["PerformanceMeasureName"].dropna()) - {""}
        missing = pm_refs - pm_names
        if missing:
            warnings.append(f"Scorecards reference missing measures: {missing}")
        rt_refs = set(sheets["Scorecards"]["RateTableName"].dropna()) - {""}
        missing = rt_refs - rt_names
        if missing:
            warnings.append(f"Scorecards reference missing rate tables: {missing}")

    # Calculation Settings → Plan Components
    if not sheets["Calculation Settings"].empty:
        refs = set(sheets["Calculation Settings"]["PlanComponentName"].dropna()) - {""}
        missing = refs - pc_names
        if missing:
            warnings.append(f"Calculation Settings reference missing plan components: {missing}")

    # Performance Measure → Credit Categories (soft check)
    if cc_names and not sheets["Performance Measure"].empty:
        refs = set(sheets["Performance Measure"]["CreditCategoryName"].dropna()) - {""}
        missing = refs - cc_names
        if missing:
            warnings.append(f"Performance Measures reference missing credit categories: {missing}")

    for w in warnings:
        logger.warning("Cross-reference: %s", w)

    return warnings


# ---------------------------------------------------------------------------
# Year suffix logic — ensures Oracle objects don't collide across plan years
# ---------------------------------------------------------------------------

def _ensure_year_suffix(name: str, year: int) -> str:
    """Add year suffix to a name if it doesn't already contain the target year.

    Examples:
        _ensure_year_suffix("Sales Commission", 2026) → "Sales Commission 2026"
        _ensure_year_suffix("Sales Commission 2025", 2026) → "Sales Commission 2026"
        _ensure_year_suffix("Sales Commission 2026", 2026) → "Sales Commission 2026"
        _ensure_year_suffix("Credit Amount", 2026) → "Credit Amount"  (generic, no year)
    """
    if not name or not name.strip():
        return name
    year_str = str(year)
    # Already has target year
    if year_str in name:
        return name
    # Has a different 4-digit year (20xx) → replace it
    import re
    match = re.search(r'\b(20\d{2})\b', name)
    if match:
        return name.replace(match.group(1), year_str)
    # No year present — only add suffix for plan-specific names (not generic ones
    # like "Credit Amount" which are reused across years).
    return name


def _apply_year_suffixes(data: Dict, plan_year: int) -> Dict:
    """Apply plan_year to object names across the oracle_mapping.

    Rules:
    - Credit categories: NEVER suffixed (reused across years)
    - Rate dimensions: NOT suffixed (tier structure is year-independent)
    - Rate tables: suffixed if they have a year already (rates change per year)
    - Expressions: suffixed (new per year to avoid collision)
    - Performance measures: suffixed (new per year, dated)
    - Plan components: suffixed (new per year, dated)
    - Compensation plans: suffixed (always year-specific)
    - Scorecards: suffixed (linked to year-specific measures)
    - Calculation settings: suffixed (linked to year-specific components)
    - Performance goals: suffixed via measure name reference
    """
    import copy
    data = copy.deepcopy(data)
    yr = plan_year

    # Build a name mapping for cross-reference consistency
    name_map: Dict[str, str] = {}

    # Expressions — always ensure year
    for expr in data.get("expressions", []):
        old = expr.get("expression_name", "")
        new = _ensure_year_suffix(old, yr)
        if old != new:
            name_map[old] = new
            expr["expression_name"] = new
        # Also update description references
        desc = expr.get("description", "")
        for old_name, new_name in name_map.items():
            if old_name in desc:
                expr["description"] = desc.replace(old_name, new_name)

    # Performance measures
    for pm in data.get("performance_measures", []):
        old = pm.get("name", "")
        new = _ensure_year_suffix(old, yr)
        if old != new:
            name_map[old] = new
            pm["name"] = new
        # Update expression references
        mfe = pm.get("measure_formula_expression_name", "")
        if mfe in name_map:
            pm["measure_formula_expression_name"] = name_map[mfe]

    # Plan components
    for pc in data.get("plan_components", []):
        old = pc.get("plan_component_name", "")
        new = _ensure_year_suffix(old, yr)
        if old != new:
            name_map[old] = new
            pc["plan_component_name"] = new
        # Update cross-references
        for ref_key in ("performance_measure_name", "incentive_formula_expression",
                        "rate_dimension_input_expression"):
            ref = pc.get(ref_key, "")
            if ref in name_map:
                pc[ref_key] = name_map[ref]
        # Plan name reference
        pn = pc.get("plan_name", "")
        if pn:
            new_pn = _ensure_year_suffix(pn, yr)
            if pn != new_pn:
                name_map[pn] = new_pn
                pc["plan_name"] = new_pn

    # Compensation plans
    for cp in data.get("compensation_plans", []):
        old = cp.get("name", "")
        new = _ensure_year_suffix(old, yr)
        if old != new:
            name_map[old] = new
            cp["name"] = new
        # Update display name
        dn = cp.get("display_name", "")
        if dn:
            cp["display_name"] = _ensure_year_suffix(dn, yr)

    # Rate tables — only suffix if they already have a year
    for rt in data.get("rate_tables", []):
        old = rt.get("rate_table_name", rt.get("table_name", ""))
        new = _ensure_year_suffix(old, yr)
        if old != new:
            name_map[old] = new
            if "rate_table_name" in rt:
                rt["rate_table_name"] = new
            if "table_name" in rt:
                rt["table_name"] = new
            if rt.get("display_name"):
                rt["display_name"] = _ensure_year_suffix(rt["display_name"], yr)

    # Rate table rates — update table name references
    for rtr in data.get("rate_table_rates", []):
        rtn = rtr.get("rate_table_name", "")
        if rtn in name_map:
            rtr["rate_table_name"] = name_map[rtn]

    # Performance goals — update measure name references
    for pg in data.get("performance_goals", []):
        pmn = pg.get("performance_measure_name", "")
        if pmn in name_map:
            pg["performance_measure_name"] = name_map[pmn]

    # Scorecards
    for sc in data.get("scorecards", []):
        sn = sc.get("scorecard_name", sc.get("name", ""))
        new_sn = _ensure_year_suffix(sn, yr)
        if sn != new_sn:
            name_map[sn] = new_sn
            if "scorecard_name" in sc:
                sc["scorecard_name"] = new_sn
            elif "name" in sc:
                sc["name"] = new_sn
        for ref_key in ("performance_measure_name", "rate_table_name",
                        "input_expression_name"):
            ref = sc.get(ref_key, "")
            if ref in name_map:
                sc[ref_key] = name_map[ref]

    # Calculation settings — update component name references
    for cs in data.get("calculation_settings", []):
        pcn = cs.get("plan_component_name", "")
        if pcn in name_map:
            cs["plan_component_name"] = name_map[pcn]

    # Expression internal references (measure_name, plan_component_name)
    for expr in data.get("expressions", []):
        for ref_key in ("measure_name", "plan_component_name"):
            ref = expr.get(ref_key, "")
            if ref and ref in name_map:
                expr[ref_key] = name_map[ref]

    # Force dates to match plan_year for all dated objects
    start_date = f"{yr}-01-01"
    end_date = f"{yr}-12-31"
    for section in ("compensation_plans", "plan_components", "performance_measures"):
        for obj in data.get(section, []):
            obj["start_date"] = start_date
            obj["end_date"] = end_date
    for pc in data.get("plan_components", []):
        pc["rt_start_date"] = start_date
        pc["rt_end_date"] = end_date
    # Update f_year for performance measures
    for pm in data.get("performance_measures", []):
        pm["f_year"] = yr

    return data


# ---------------------------------------------------------------------------
# Internal builders — each produces a DataFrame with exact column names
# ---------------------------------------------------------------------------

def _build_rate_dimensions(data: Dict, org_id: int) -> pd.DataFrame:
    rows = []
    for rd in data.get("rate_dimensions", []):
        rows.append({
            "Rate Dimension Name": rd.get("rate_dimension_name", rd.get("name", "")),
            "Rate Dimension Type": rd.get("rate_dimension_type", "AMOUNT"),
            "Org ID": org_id,
            "Tier Sequence": rd.get("tier_sequence", 1),
            "Minimum Amount": rd.get("minimum_amount", 0),
            "Maximum Amount": rd.get("maximum_amount", 999999),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Rate Dimension"])


def _build_rate_tables(data: Dict, org_id: int) -> pd.DataFrame:
    # Build mapping from rate table name → rate dimension name.
    # Strategy: match rate_table_rates ranges to rate_dimension tier ranges.
    dim_names = sorted({d.get("rate_dimension_name", "") for d in data.get("rate_dimensions", [])})
    # Group rate_table_rates by table name
    rtr_by_table: Dict[str, list] = {}
    for rtr in data.get("rate_table_rates", []):
        rtr_by_table.setdefault(rtr.get("rate_table_name", ""), []).append(rtr)
    # Group rate_dimensions by name
    dims_by_name: Dict[str, list] = {}
    for rd in data.get("rate_dimensions", []):
        dims_by_name.setdefault(rd.get("rate_dimension_name", ""), []).append(rd)

    def _match_dimension(table_name: str) -> str:
        """Find the rate dimension whose tiers align with this table's rates."""
        rates = rtr_by_table.get(table_name, [])
        rate_ranges = sorted((r.get("minimum_amount", 0), r.get("maximum_amount", 0)) for r in rates)
        for dname, dtiers in dims_by_name.items():
            dim_ranges = sorted((d.get("minimum_amount", 0), d.get("maximum_amount", 0)) for d in dtiers)
            if dim_ranges == rate_ranges:
                return dname
        # Fallback: if only one dimension exists, use it
        if len(dim_names) == 1:
            return dim_names[0]
        return ""

    rows = []
    for rt in data.get("rate_tables", []):
        name = rt.get("rate_table_name", rt.get("table_name", ""))
        rows.append({
            "Rate Table Name": name,
            "Rate Table Type": rt.get("rate_table_type", "PERCENT"),
            "Org ID": org_id,
            "Display Name": rt.get("display_name", name),
            "Rate Dimension Name": _match_dimension(name),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Rate Table"])


def _build_rate_table_rates(data: Dict) -> pd.DataFrame:
    rows = []
    for rtr in data.get("rate_table_rates", []):
        rows.append({
            "Rate Table Name": rtr.get("rate_table_name", ""),
            "Minimum Amount": rtr.get("minimum_amount", 0),
            "Maximum Amount": rtr.get("maximum_amount", 999999),
            "Rate Value": rtr.get("rate_value", 0.0),
            "TierSequence": rtr.get("tier_sequence", 1),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Rate Table Rates"])


def _build_expressions(data: Dict) -> pd.DataFrame:
    rows = []
    for i, expr in enumerate(data.get("expressions", []), start=1):
        rows.append({
            "Expression Name": expr.get("expression_name", ""),
            "Expression ID": expr.get("expression_id", i),
            "Expression Detail Type": expr.get("expression_detail_type", "Calculation"),
            "Description": expr.get("description", ""),
            "Expression Type": expr.get("expression_type", "Calculation"),
            "ExpressionCategory": expr.get("expression_category", "Earnings"),
            "Sequence": expr.get("sequence", i),
            "Measure Name": expr.get("measure_name"),
            "Basic Attributes Group": expr.get("basic_attributes_group"),
            "Basic Attribute Name": expr.get("basic_attribute_name"),
            "Measure Result Attribute": expr.get("measure_result_attribute"),
            "Plan Component Name": expr.get("plan_component_name"),
            "Plan Component Result Attribute": expr.get("plan_component_result_attribute"),
            "Constant Value": expr.get("constant_value"),
            "Expression Operator": expr.get("expression_operator"),
            "Expression Detail ID": expr.get("expression_detail_id", i),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Expression"])


def _build_performance_measures(
    data: Dict, org_id: int, plan_year: int,
    start_date: str, end_date: str,
) -> pd.DataFrame:
    rows = []
    for pm in data.get("performance_measures", []):
        rows.append({
            "Name": pm.get("name", ""),
            "Description": pm.get("description", ""),
            "UnitOfMeasure": pm.get("unit_of_measure", "AMOUNT"),
            "OrgId": org_id,
            "StartDate": pm.get("start_date", start_date),
            "EndDate": pm.get("end_date", end_date),
            "MeasureFormulaExpressionName": pm.get("measure_formula_expression_name"),
            "ProcessTransactions": pm.get("process_transactions", "Yes"),
            "PerformanceInterval": pm.get("performance_interval", "Quarterly"),
            "ActiveFlag": pm.get("active_flag", "Y"),
            "UseExternalFormulaFlag": pm.get("use_external_formula_flag", "N"),
            "RunningTotalFlag": pm.get("running_total_flag", "N"),
            "FYear": pm.get("f_year", plan_year),
            "CreditCategoryName": pm.get("credit_category_name", "Sales Credit"),
            "ScorecardRateTableName": pm.get("scorecard_rate_table_name"),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Performance Measure"])


def _build_plan_components(
    data: Dict, org_id: int, start_date: str, end_date: str,
) -> pd.DataFrame:
    rows = []
    for i, pc in enumerate(data.get("plan_components", []), start=1):
        rows.append({
            "PlanName": pc.get("plan_name", ""),
            "Plan Component Name": pc.get("plan_component_name", ""),
            "IncentiveType": pc.get("incentive_type", "Sales"),
            "StartDate": pc.get("start_date", start_date),
            "EndDate": pc.get("end_date", end_date),
            "CalculationMethod": pc.get("calculation_method", "Tiered"),
            "OrgId": org_id,
            "Performance Measure Name": pc.get("performance_measure_name", ""),
            "Rate Table Name": pc.get("rate_table_name", ""),
            "RTStartDate": pc.get("rt_start_date", start_date),
            "RTEndDate": pc.get("rt_end_date", end_date),
            "Incentive Formula Expression": pc.get("incentive_formula_expression", ""),
            "PerformanceMeasureWeight": pc.get("performance_measure_weight", 1.0),
            "CalculationSequence": pc.get("calculation_sequence", i),
            "EarningBasis": pc.get("earning_basis", "Amount"),
            # Advanced calculation settings (Oracle API field types)
            # CalculateIncentive: string lookup (CN_PLAN_INCENTIVE_TYPE) — BONUS or COMMISSION
            "CalculateIncentive": pc.get("calculate_incentive", "COMMISSION"),
            # CalculationPhase: integer (1=Phase 1, 2=Phase 2) — CN_CALCULATION_PHASE
            "Calculation Phase": int(pc.get("calculation_phase", 1)),
            # EarningType: integer (-1000=Monetary earnings) — EarningTypesVO
            "Earning Type": int(pc.get("earning_type", -1000)),
            "PayoutFrequency": pc.get("payout_frequency", "Period"),
            "SplitAttainment": pc.get("split_attainment", "No"),
            "FixedWithinTier": pc.get("fixed_within_tier", "No"),
            "TrueUp": pc.get("true_up", "No"),
            "TrueUpResetInterval": pc.get("true_up_reset_interval"),
            "IncludeIndirectCredits": pc.get("include_indirect_credits", "None"),
            "RateDimensionInputExpression": pc.get("rate_dimension_input_expression"),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Plan Components"])


def _build_compensation_plans(
    data: Dict, org_id: int, start_date: str, end_date: str,
) -> pd.DataFrame:
    # Build reverse map: plan_name -> list of component names
    plan_to_components: Dict[str, list] = {}
    for pc in data.get("plan_components", []):
        pn = pc.get("plan_name", "")
        cn = pc.get("plan_component_name", pc.get("name", ""))
        if pn and cn:
            plan_to_components.setdefault(pn, []).append(cn)

    rows = []
    for cp in data.get("compensation_plans", []):
        name = cp.get("name", "")
        component_names = plan_to_components.get(name, [])
        if component_names:
            # One row per component so each gets linked during deployment
            for comp_name in component_names:
                rows.append({
                    "Name": name,
                    "StartDate": cp.get("start_date", start_date),
                    "EndDate": cp.get("end_date", end_date),
                    "Status": cp.get("status", "Active"),
                    "Description": cp.get("description", ""),
                    "DisplayName": cp.get("display_name", name),
                    "TargetIncentive": cp.get("target_incentive", 0),
                    "OrgId": org_id,
                    "Plan Component Name": comp_name,
                })
        else:
            rows.append({
                "Name": name,
                "StartDate": cp.get("start_date", start_date),
                "EndDate": cp.get("end_date", end_date),
                "Status": cp.get("status", "Active"),
                "Description": cp.get("description", ""),
                "DisplayName": cp.get("display_name", name),
                "TargetIncentive": cp.get("target_incentive", 0),
                "OrgId": org_id,
                "Plan Component Name": "",
            })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Compensation Plans"])


def _build_performance_goals(data: Dict) -> pd.DataFrame:
    rows = []
    for pg in data.get("performance_goals", []):
        rows.append({
            "PerformanceMeasureName": pg.get("performance_measure_name", ""),
            "GoalInterval": pg.get("goal_interval", "Quarterly"),
            "GoalTarget": pg.get("goal_target", 0),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Performance Goals"])


def _build_credit_categories(data: Dict, org_id: int) -> pd.DataFrame:
    rows = []
    for cc in data.get("credit_categories", []):
        # Action: "reuse" (exists in Oracle), "create" (new), or
        # "create_with_mapping" (new + needs data migration/backward integration)
        action = cc.get("action", "reuse")
        rows.append({
            "CreditCategoryName": cc.get("credit_category_name", cc.get("name", "")),
            "Description": cc.get("description", ""),
            "OrgId": org_id,
            "Action": action,
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Credit Categories"])


def _build_scorecards(data: Dict) -> pd.DataFrame:
    rows = []
    for sc in data.get("scorecards", []):
        rows.append({
            "ScorecardName": sc.get("scorecard_name", sc.get("name", "")),
            "PerformanceMeasureName": sc.get("performance_measure_name", ""),
            "RateTableName": sc.get("rate_table_name", ""),
            "InputExpressionName": sc.get("input_expression_name", ""),
            "Description": sc.get("description", ""),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Scorecards"])


def _build_calculation_settings(data: Dict) -> pd.DataFrame:
    rows = []
    for cs in data.get("calculation_settings", []):
        rows.append({
            "PlanComponentName": cs.get("plan_component_name", ""),
            "CalculateIncentive": cs.get("calculate_incentive", "Per interval"),
            "ProcessTransactions": cs.get("process_transactions", "Grouped by interval"),
            "PayoutFrequency": cs.get("payout_frequency", "Period"),
            "SplitAttainment": cs.get("split_attainment", "No"),
            "FixedWithinTier": cs.get("fixed_within_tier", "No"),
            "TrueUp": cs.get("true_up", "No"),
            "TrueUpResetInterval": cs.get("true_up_reset_interval"),
            "IncludeIndirectCredits": cs.get("include_indirect_credits", "None"),
            "RunningTotal": cs.get("running_total", "No"),
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Calculation Settings"])


def _build_config(org_id: int, plan_year: int) -> pd.DataFrame:
    rows = [
        {"Key": "Version", "Value": "2.0"},
        {"Key": "Year", "Value": str(plan_year)},
        {"Key": "OrgId", "Value": str(org_id)},
        {"Key": "GeneratedBy", "Value": "PlanLytics AI"},
        {"Key": "GeneratedAt", "Value": datetime.now().isoformat()},
    ]
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Config"])
