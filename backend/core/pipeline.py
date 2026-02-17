# core/pipeline.py
import json
import uuid
import logging
from pathlib import Path
from .parsing import extract_text
from .prompting import build_prompt, call_llm
from .mapping_oracle import infer_oracle_objects

logger = logging.getLogger(__name__)


def run_analysis(file_path: Path, template: str) -> dict:
    text = extract_text(file_path)
    prompt = build_prompt(text, template)
    raw = call_llm(prompt)
    # parse JSON safely
    try:
        analysis = json.loads(raw.strip())
    except Exception:
        raw_json = raw[raw.find("{"): raw.rfind("}")+1]
        analysis = json.loads(raw_json)
    analysis["template"] = template
    analysis = infer_oracle_objects(analysis)
    return analysis


def run_analysis_for_icm(
    file_path: Path,
    template: str = "oracle_mapping",
    org_id: int = 300000046987012,
    plan_year: int = None,
) -> dict:
    """
    Run analysis pipeline and produce ICM Optimizer-ready output.

    Returns dict with:
        - analysis_id: unique identifier
        - analysis: the full AI analysis JSON
        - icm_workbook_bytes: bytes of the Excel file
        - validation_warnings: list of cross-reference issues
    """
    from .icm_transformer import (
        transform_analysis_to_icm_workbook,
        write_icm_workbook,
        validate_cross_references,
    )

    # Step 1: Run standard analysis (uses LLM with new ICM-aware prompts)
    analysis = run_analysis(file_path, template)

    # Step 2: Transform to ICM workbook format
    icm_sheets = transform_analysis_to_icm_workbook(
        analysis, org_id=org_id, plan_year=plan_year,
    )

    # Step 3: Validate cross-references
    warnings = validate_cross_references(icm_sheets)

    # Step 4: Generate workbook bytes
    workbook_bytes = write_icm_workbook(icm_sheets)

    analysis_id = uuid.uuid4().hex[:12]

    return {
        "analysis_id": analysis_id,
        "analysis": analysis,
        "icm_workbook_bytes": workbook_bytes,
        "validation_warnings": warnings,
    }
