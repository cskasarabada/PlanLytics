import os
import json
import requests
from typing import Optional

# -----------------------------
# Config via environment
# -----------------------------
# Choose backend: "openai", "ollama", or "stub"
LLM_BACKEND = os.getenv("LLM_BACKEND", "stub").lower()

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Ollama settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Common generation settings
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

SYSTEM_ROLE = (
    "You are an Incentive Compensation Automation Analyst. "
    "Extract plan mechanics, risks, stakeholder questions, and translate them into "
    "vendor-neutral requirements, then map to Oracle ICM objects. "
    "Return compact JSON ONLY that matches required schema fields. Do not invent facts."
)

# -----------------------------
# Backends
# -----------------------------

def _call_openai(prompt: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_ROLE},
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post(f"{OPENAI_BASE}/chat/completions", headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_ollama(prompt: str) -> str:
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_ROLE},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": TEMPERATURE},
        "stream": False,
    }
    resp = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # Newer Ollama chat API returns { message: { role, content } }
    if isinstance(data, dict) and "message" in data:
        return data["message"]["content"]
    # Older response formats
    return data.get("response", "{}")


def _call_stub(_: str) -> str:
    # Minimal, valid JSON to keep the pipeline running without a model
    sample = {
        "template": "master",
        "plan_structure": [
            {"name": "Eligibility", "description": "Who is eligible for commissions", "raw_excerpt": ""},
            {"name": "Transactions", "description": "Invoice-based crediting", "raw_excerpt": ""},
        ],
        "risks": [
            {"title": "Discretionary wording", "severity": "medium", "detail": "Ambiguous terms found", "raw_excerpt": ""}
        ],
        "stakeholder_questions": [
            "Confirm invoice vs. order credit basis?",
            "Provide clawback/return rules?",
        ],
        "oracle_mapping": {
            "participants": [{"fields": ["EmployeeId", "Name", "Role", "Territory", "StartDate", "EndDate"]}],
            "transactions": [{
                "name": "InvoiceTxn", "source": "Invoice",
                "keys": ["InvoiceNumber", "InvoiceDate", "Customer", "Item", "Amount"]
            }],
            "credit_rules": [{"basis": "line", "allocation": "full", "holdback_days": 0}],
            "rate_tables": [{"dimensions": ["ProductClass", "AttainmentBand"], "outputs": ["Rate%"]}],
            "plan_elements": [{"type": "Commission", "frequency": "Monthly"}],
            "roles": [{"name": "SalesRep"}, {"name": "Manager"}]
        },
        "reports_recommendations": ["Rep statements with drill-through"],
        "governance_controls": ["Versioned plan docs"],
        "operational_flexibility": ["Effective-dated territories"],
        "data_integrations": ["ERP Orders/Invoices", "HRIS Participants"],
        "side_by_side_rows": [
            {"Plan Element": "Invoice credited at line", "Requirement": "Line-level crediting", "Vendor/System Feature Needed": "Credit Rules + Keys"}
        ],
        "vendor_compare_rows": []
    }
    return json.dumps(sample)


# -----------------------------
# Public API
# -----------------------------

def call_llm(prompt: str, temperature: Optional[float] = None) -> str:
    """Call the configured LLM backend and return raw text (expected JSON)."""
    global TEMPERATURE
    if temperature is not None:
        TEMPERATURE = temperature

    backend = LLM_BACKEND
    try:
        if backend == "openai":
            return _call_openai(prompt)
        if backend == "ollama":
            return _call_ollama(prompt)
        # default to stub
        return _call_stub(prompt)
    except Exception as e:
        # graceful fallback: if real model fails, use stub so user can continue
        return _call_stub(prompt)


def build_prompt(plan_text: str, template: str) -> str:
    """Instruction tuned to produce our analysis JSON."""
    return f"""
Required Output Template: {template}

Return JSON with the following fields:
- plan_structure[] (name, description, raw_excerpt)
- risks[] (title, severity, detail, raw_excerpt)
- stakeholder_questions[]
- oracle_mapping {{ participants[], transactions[], credit_rules[], rate_tables[], plan_elements[], roles[] }}
- reports_recommendations[], governance_controls[], operational_flexibility[], data_integrations[]
- side_by_side_rows[]
- vendor_compare_rows[] (only when template = side_by_side_vendor_compare)

Rules:
- Output MUST be valid JSON (no prose). If unknown, leave arrays empty.
- Use concise, accurate entries. Include short exact excerpts when available.
- Do not assume invoice-based crediting unless present in the text.

Plan Document (verbatim, truncated if long):
<<<
{plan_text[:120000]}
>>>
""".strip()
