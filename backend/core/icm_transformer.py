# core/icm_transformer.py
"""
Transforms PlanLytics AI analysis JSON into an ICM Optimizer-compatible
Excel workbook with the exact 9 worksheets and column names expected.
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
    "Rate Dimension": [
        "Rate Dimension Name", "Rate Dimension Type", "Org ID",
        "Tier Sequence", "Minimum Amount", "Maximum Amount",
    ],
    "Rate Table": [
        "Rate Table Name", "Rate Table Type", "Org ID", "Display Name",
    ],
    "Rate Table Rates": [
        "Rate Table Name", "Minimum Amount", "Maximum Amount",
        "Rate Value", "TierSequence",
    ],
    "Expression": [
        "Expression Name", "Expression ID", "Expression Detail Type",
        "Description", "Expression Type", "Sequence", "Measure Name",
        "Basic Attributes Group", "Basic Attribute Name",
        "Measure Result Attribute", "Plan Component Name",
        "Plan Component Result Attribute", "Constant Value",
        "Expression Operator", "Expression Detail ID",
    ],
    "Performance Measure": [
        "Name", "Description", "UnitOfMeasure", "OrgId", "StartDate",
        "EndDate", "MeasureFormulaExpressionName", "ProcessTransactions",
        "PerformanceInterval", "ActiveFlag", "UseExternalFormulaFlag",
        "RunningTotalFlag", "FYear", "CreditCategoryName",
    ],
    "Plan Components": [
        "PlanName", "Plan Component Name", "IncentiveType", "StartDate",
        "EndDate", "CalculationMethod", "OrgId", "Performance Measure Name",
        "Rate Table Name", "RTStartDate", "RTEndDate",
        "Incentive Formula Expression", "PerformanceMeasureWeight",
        "CalculationSequence", "EarningBasis",
    ],
    "Compensation Plans": [
        "Name", "StartDate", "EndDate", "Status", "Description",
        "DisplayName", "TargetIncentive", "OrgId",
    ],
    "Performance Goals": [
        "PerformanceMeasureName", "GoalInterval", "GoalTarget",
    ],
    "Config": [
        "Key", "Value",
    ],
}


def transform_analysis_to_icm_workbook(
    analysis_json: Dict[str, Any],
    org_id: int = 300000046987012,
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

    sheets = {}
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

    if not sheets["Compensation Plans"].empty:
        plan_names = set(sheets["Compensation Plans"]["Name"].dropna())
    if not sheets["Rate Table"].empty:
        rt_names = set(sheets["Rate Table"]["Rate Table Name"].dropna())
    if not sheets["Performance Measure"].empty:
        pm_names = set(sheets["Performance Measure"]["Name"].dropna())

    # Plan Components → Compensation Plans
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["PlanName"].dropna())
        missing = refs - plan_names
        if missing:
            warnings.append(f"Plan Components reference missing plans: {missing}")

    # Plan Components → Rate Tables
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["Rate Table Name"].dropna())
        missing = refs - rt_names
        if missing:
            warnings.append(f"Plan Components reference missing rate tables: {missing}")

    # Plan Components → Performance Measures
    if not sheets["Plan Components"].empty:
        refs = set(sheets["Plan Components"]["Performance Measure Name"].dropna())
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

    for w in warnings:
        logger.warning("Cross-reference: %s", w)

    return warnings


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
    rows = []
    for rt in data.get("rate_tables", []):
        name = rt.get("rate_table_name", rt.get("table_name", ""))
        rows.append({
            "Rate Table Name": name,
            "Rate Table Type": rt.get("rate_table_type", "Sales"),
            "Org ID": org_id,
            "Display Name": rt.get("display_name", name),
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
        })
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Plan Components"])


def _build_compensation_plans(
    data: Dict, org_id: int, start_date: str, end_date: str,
) -> pd.DataFrame:
    rows = []
    for cp in data.get("compensation_plans", []):
        name = cp.get("name", "")
        rows.append({
            "Name": name,
            "StartDate": cp.get("start_date", start_date),
            "EndDate": cp.get("end_date", end_date),
            "Status": cp.get("status", "Active"),
            "Description": cp.get("description", ""),
            "DisplayName": cp.get("display_name", name),
            "TargetIncentive": cp.get("target_incentive", 0),
            "OrgId": org_id,
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


def _build_config(org_id: int, plan_year: int) -> pd.DataFrame:
    rows = [
        {"Key": "Version", "Value": "1.0"},
        {"Key": "Year", "Value": str(plan_year)},
        {"Key": "OrgId", "Value": str(org_id)},
        {"Key": "GeneratedBy", "Value": "PlanLytics AI"},
        {"Key": "GeneratedAt", "Value": datetime.now().isoformat()},
    ]
    return pd.DataFrame(rows, columns=SHEET_COLUMNS["Config"])
