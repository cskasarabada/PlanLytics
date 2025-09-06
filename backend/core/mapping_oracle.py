# core/mapping_oracle.py
def infer_oracle_objects(analysis_json: dict) -> dict:
    # Ensure required sub-objects exist and add safe defaults if missing
    om = analysis_json.setdefault("oracle_mapping", {})
    om.setdefault("participants", [{"fields":["EmployeeId","Name","Role","Territory","StartDate","EndDate"]}])
    om.setdefault("transactions", [{"name":"InvoiceTxn","source":"Invoice","keys":["InvoiceNumber","InvoiceDate","Customer","Item","Amount"]}])
    om.setdefault("credit_rules", [{"basis":"line","allocation":"full","holdback_days":0}])
    om.setdefault("rate_tables", [{"dimensions":["ProductClass","AttainmentBand"],"outputs":["Rate%"]}])
    om.setdefault("plan_elements", [{"type":"Commission","frequency":"Monthly"}])
    om.setdefault("roles", [{"name":"SalesRep"},{"name":"Manager"}])
    return analysis_json
