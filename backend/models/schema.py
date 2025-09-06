cat > models/schemas.py << 'PY'
from pydantic import BaseModel
from typing import List, Literal, Dict, Any

TemplateName = Literal[
    "automation_framework",
    "vendor_checklist",
    "side_by_side",
    "master",
    "side_by_side_vendor_compare"
]

class PlanElement(BaseModel):
    name: str
    description: str
    raw_excerpt: str

class RiskItem(BaseModel):
    title: str
    severity: Literal["low","medium","high"]
    detail: str
    raw_excerpt: str

class OracleMapping(BaseModel):
    participants: List[Dict[str, Any]] = []
    transactions: List[Dict[str, Any]] = []
    credit_rules: List[Dict[str, Any]] = []
    rate_tables: List[Dict[str, Any]] = []
    plan_elements: List[Dict[str, Any]] = []
    roles: List[Dict[str, Any]] = []

class AnalysisOutput(BaseModel):
    template: TemplateName
    plan_structure: List[PlanElement] = []
    risks: List[RiskItem] = []
    stakeholder_questions: List[str] = []
    oracle_mapping: OracleMapping = OracleMapping()
    reports_recommendations: List[str] = []
    governance_controls: List[str] = []
    operational_flexibility: List[str] = []
    data_integrations: List[str] = []
    side_by_side_rows: List[Dict[str, str]] = []
    vendor_compare_rows: List[Dict[str, str]] = []
PY
