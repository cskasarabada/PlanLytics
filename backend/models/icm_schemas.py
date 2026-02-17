# models/icm_schemas.py - Pydantic models matching ICM Optimizer Excel worksheets
"""
These models mirror the exact column names expected by the ICM Optimizer
Excel workbook (PlanData.py). Each model corresponds to one worksheet.

12 sheets covering the full Oracle ICM object hierarchy:
  Credit Categories, Rate Dimension, Rate Table, Rate Table Rates,
  Expression, Performance Measure, Plan Components, Compensation Plans,
  Performance Goals, Scorecards, Calculation Settings, Config
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ICMCreditCategory(BaseModel):
    """Sheet: 'Credit Categories' — credit category definitions."""
    credit_category_name: str
    description: str = ""
    org_id: int = 0


class ICMRateDimension(BaseModel):
    """Sheet: 'Rate Dimension' — defines tier boundaries for rate lookups."""
    rate_dimension_name: str
    rate_dimension_type: str = "AMOUNT"
    org_id: int = 0
    tier_sequence: int = 1
    minimum_amount: float = 0.0
    maximum_amount: float = 999999.0


class ICMRateTable(BaseModel):
    """Sheet: 'Rate Table' — defines rate table containers."""
    rate_table_name: str
    rate_table_type: str = "Sales"
    org_id: int = 0
    display_name: str = ""


class ICMRateTableRate(BaseModel):
    """Sheet: 'Rate Table Rates' — individual rate values per tier."""
    rate_table_name: str
    minimum_amount: float = 0.0
    maximum_amount: float = 999999.0
    rate_value: float = 0.0
    tier_sequence: int = 1


class ICMExpression(BaseModel):
    """Sheet: 'Expression' — calculation formula definitions.

    ExpressionCategory values:
      - Attainment: e.g. SUM(Credit.Credit Amount / Measure.Interval Target)
      - Earnings: e.g. Measure.ITD Output Achieved * RTR
      - RateDimensionInput: e.g. Measure result.<name>.ITD Output Achieved
      - Weighted: e.g. SUM(Credit.Credit Amount * Measure.Weight)
    """
    expression_name: str
    expression_id: Optional[int] = None
    expression_detail_type: str = "Calculation"
    description: str = ""
    expression_type: str = "Calculation"
    expression_category: str = "Earnings"
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
    org_id: int = 0
    start_date: str = ""
    end_date: str = ""
    measure_formula_expression_name: Optional[str] = None
    process_transactions: str = "GROUP"
    performance_interval: str = "-1001"
    active_flag: str = "Y"
    use_external_formula_flag: str = "N"
    running_total_flag: str = "N"
    f_year: int = 0
    credit_category_name: str = "Sales Credit"
    scorecard_rate_table_name: Optional[str] = None


class ICMPlanComponent(BaseModel):
    """Sheet: 'Plan Components' — links plans to measures, rates, formulas.

    Advanced calculation settings:
      - calculate_incentive: 'Per interval' (bonus) or 'Per event' (commission)
      - payout_frequency: Period, Quarter, Annual, Biweekly
      - split_attainment: Yes/No
      - fixed_within_tier: Yes/No (only when split_attainment=Yes)
      - true_up: Yes/No — subtracts previously paid from current calculated
      - true_up_reset_interval: e.g. Annual (when true_up=Yes)
      - include_indirect_credits: None, All, or specific category name
      - rate_dimension_input_expression: expression name for rate dimension input
    """
    plan_name: str
    plan_component_name: str
    incentive_type: str = "Sales"
    start_date: str = ""
    end_date: str = ""
    calculation_method: str = "Tiered"
    org_id: int = 0
    performance_measure_name: str = ""
    rate_table_name: str = ""
    rt_start_date: str = ""
    rt_end_date: str = ""
    incentive_formula_expression: str = ""
    performance_measure_weight: float = 1.0
    calculation_sequence: int = 1
    earning_basis: str = "Amount"
    calculate_incentive: str = "Per interval"
    payout_frequency: str = "Period"
    split_attainment: str = "No"
    fixed_within_tier: str = "No"
    true_up: str = "No"
    true_up_reset_interval: Optional[str] = None
    include_indirect_credits: str = "None"
    rate_dimension_input_expression: Optional[str] = None


class ICMCompensationPlan(BaseModel):
    """Sheet: 'Compensation Plans' — top-level plan containers."""
    name: str
    start_date: str = ""
    end_date: str = ""
    status: str = "Active"
    description: str = ""
    display_name: str = ""
    target_incentive: float = 0.0
    org_id: int = 0


class ICMPerformanceGoal(BaseModel):
    """Sheet: 'Performance Goals' — targets for each measure."""
    performance_measure_name: str
    goal_interval: str = "Quarterly"
    goal_target: float = 0.0


class ICMScorecard(BaseModel):
    """Sheet: 'Scorecards' — maps measures to scorecard rate tables.

    Used in Weighted Score Bonus patterns where a performance measure's
    output is converted to a score via a scorecard rate table.
    """
    scorecard_name: str
    performance_measure_name: str = ""
    rate_table_name: str = ""
    input_expression_name: str = ""
    description: str = ""


class ICMCalculationSetting(BaseModel):
    """Sheet: 'Calculation Settings' — advanced per-component settings.

    Captures Oracle ICM calculation options:
      - calculate_incentive: Per interval or Per event
      - process_transactions: Grouped by interval or Individually
      - payout_frequency: Period, Quarter, Annual, Biweekly
      - split_attainment: Yes/No
      - fixed_within_tier: Yes/No
      - true_up: Yes/No
      - true_up_reset_interval: Annual, Quarterly, etc.
      - include_indirect_credits: None, All, or specific
      - running_total: Yes/No
    """
    plan_component_name: str
    calculate_incentive: str = "Per interval"
    process_transactions: str = "Grouped by interval"
    payout_frequency: str = "Period"
    split_attainment: str = "No"
    fixed_within_tier: str = "No"
    true_up: str = "No"
    true_up_reset_interval: Optional[str] = None
    include_indirect_credits: str = "None"
    running_total: str = "No"


class ICMConfigEntry(BaseModel):
    """Sheet: 'Config' — key/value metadata."""
    key: str
    value: str


class ICMWorkbookData(BaseModel):
    """Complete workbook data — all 12 sheets."""
    credit_categories: List[ICMCreditCategory] = []
    rate_dimensions: List[ICMRateDimension] = []
    rate_tables: List[ICMRateTable] = []
    rate_table_rates: List[ICMRateTableRate] = []
    expressions: List[ICMExpression] = []
    performance_measures: List[ICMPerformanceMeasure] = []
    plan_components: List[ICMPlanComponent] = []
    compensation_plans: List[ICMCompensationPlan] = []
    performance_goals: List[ICMPerformanceGoal] = []
    scorecards: List[ICMScorecard] = []
    calculation_settings: List[ICMCalculationSetting] = []
    config: List[ICMConfigEntry] = []
