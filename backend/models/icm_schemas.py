# models/icm_schemas.py - Pydantic models matching ICM Optimizer Excel worksheets
"""
These models mirror the exact column names expected by the ICM Optimizer
Excel workbook (PlanData.py). Each model corresponds to one worksheet.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ICMRateDimension(BaseModel):
    """Sheet: 'Rate Dimension' — defines tier boundaries for rate lookups."""
    rate_dimension_name: str
    rate_dimension_type: str = "AMOUNT"
    org_id: int = 300000046987012
    tier_sequence: int = 1
    minimum_amount: float = 0.0
    maximum_amount: float = 999999.0


class ICMRateTable(BaseModel):
    """Sheet: 'Rate Table' — defines rate table containers."""
    rate_table_name: str
    rate_table_type: str = "Sales"
    org_id: int = 300000046987012
    display_name: str = ""


class ICMRateTableRate(BaseModel):
    """Sheet: 'Rate Table Rates' — individual rate values per tier."""
    rate_table_name: str
    minimum_amount: float = 0.0
    maximum_amount: float = 999999.0
    rate_value: float = 0.0
    tier_sequence: int = 1


class ICMExpression(BaseModel):
    """Sheet: 'Expression' — calculation formula definitions."""
    expression_name: str
    expression_id: Optional[int] = None
    expression_detail_type: str = "Calculation"
    description: str = ""
    expression_type: str = "Calculation"
    sequence: int = 1
    measure_name: Optional[str] = None
    basic_attributes_group: Optional[str] = None
    basic_attribute_name: Optional[str] = None
    measure_result_attribute: Optional[str] = None
    plan_component_name: Optional[str] = None
    plan_component_result_attribute: Optional[str] = None
    constant_value: Optional[float] = None
    expression_operator: Optional[str] = None
    expression_detail_id: Optional[int] = None


class ICMPerformanceMeasure(BaseModel):
    """Sheet: 'Performance Measure' — what gets measured and credited."""
    name: str
    description: str = ""
    unit_of_measure: str = "AMOUNT"
    org_id: int = 300000046987012
    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"
    measure_formula_expression_name: Optional[str] = None
    process_transactions: str = "Yes"
    performance_interval: str = "Quarterly"
    active_flag: str = "Y"
    use_external_formula_flag: str = "N"
    running_total_flag: str = "N"
    f_year: int = 2025
    credit_category_name: str = "Sales Credit"


class ICMPlanComponent(BaseModel):
    """Sheet: 'Plan Components' — links plans to measures, rates, formulas."""
    plan_name: str
    plan_component_name: str
    incentive_type: str = "Sales"
    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"
    calculation_method: str = "Tiered"
    org_id: int = 300000046987012
    performance_measure_name: str = ""
    rate_table_name: str = ""
    rt_start_date: str = "2025-01-01"
    rt_end_date: str = "2025-12-31"
    incentive_formula_expression: str = ""
    performance_measure_weight: float = 1.0
    calculation_sequence: int = 1
    earning_basis: str = "Amount"


class ICMCompensationPlan(BaseModel):
    """Sheet: 'Compensation Plans' — top-level plan containers."""
    name: str
    start_date: str = "2025-01-01"
    end_date: str = "2025-12-31"
    status: str = "Active"
    description: str = ""
    display_name: str = ""
    target_incentive: float = 0.0
    org_id: int = 300000046987012


class ICMPerformanceGoal(BaseModel):
    """Sheet: 'Performance Goals' — targets for each measure."""
    performance_measure_name: str
    goal_interval: str = "Quarterly"
    goal_target: float = 0.0


class ICMConfigEntry(BaseModel):
    """Sheet: 'Config' — key/value metadata."""
    key: str
    value: str


class ICMWorkbookData(BaseModel):
    """Complete workbook data — all 9 sheets."""
    rate_dimensions: List[ICMRateDimension] = []
    rate_tables: List[ICMRateTable] = []
    rate_table_rates: List[ICMRateTableRate] = []
    expressions: List[ICMExpression] = []
    performance_measures: List[ICMPerformanceMeasure] = []
    plan_components: List[ICMPlanComponent] = []
    compensation_plans: List[ICMCompensationPlan] = []
    performance_goals: List[ICMPerformanceGoal] = []
    config: List[ICMConfigEntry] = []
