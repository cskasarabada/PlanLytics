# core/pipeline.py
import json
import uuid
import logging
from pathlib import Path
from .parsing import extract_text
from .prompting import build_prompt, call_llm
from .mapping_oracle import infer_oracle_objects

logger = logging.getLogger(__name__)


def run_analysis(
    file_path: Path = None,
    template: str = "oracle_mapping",
    text: str = None,
    plan_year: int = None,
    org_id: int = 0,
) -> dict:
    if text is None:
        if file_path is None:
            raise ValueError("Either file_path or text must be provided")
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
    analysis = infer_oracle_objects(analysis, org_id=org_id, plan_year=plan_year)
    return analysis


def run_analysis_for_icm(
    file_path: Path = None,
    template: str = "oracle_mapping",
    org_id: int = 0,
    plan_year: int = None,
    text: str = None,
) -> dict:
    """
    Run analysis pipeline and produce ICM Optimizer-ready output.

    Provide EITHER file_path OR text.  If text is given, file_path is ignored.

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
    analysis = run_analysis(file_path, template, text=text, plan_year=plan_year, org_id=org_id)

    # Step 2: Transform to ICM workbook format
    icm_sheets = transform_analysis_to_icm_workbook(
        analysis, org_id=org_id, plan_year=plan_year,
    )

    # Step 3: Validate cross-references
    warnings = validate_cross_references(icm_sheets)

    # Step 4: Generate workbook bytes
    workbook_bytes = write_icm_workbook(icm_sheets)

    analysis_id = uuid.uuid4().hex[:12]

    # Step 5: Generate Design Document and Configuration Document
    from .doc_generator import generate_design_document, generate_config_document

    # Attach validation_warnings to analysis so doc_generator can access them
    analysis["validation_warnings"] = warnings

    design_doc_bytes = generate_design_document(analysis, analysis_id)
    config_doc_bytes = generate_config_document(analysis, analysis_id)

    # Generate efficiency report and XML export for all analysis paths
    from .efficiency_report import analyze_efficiency, generate_efficiency_report_doc
    from .xml_exporter import generate_icm_xml

    efficiency = analyze_efficiency(analysis.get("oracle_mapping", {}))
    efficiency_doc_bytes = generate_efficiency_report_doc(efficiency, analysis, analysis_id)
    xml_export_bytes = generate_icm_xml(
        analysis.get("oracle_mapping", {}),
        org_id=org_id,
        plan_year=plan_year,
    )

    return {
        "analysis_id": analysis_id,
        "analysis": analysis,
        "icm_workbook_bytes": workbook_bytes,
        "design_doc_bytes": design_doc_bytes,
        "config_doc_bytes": config_doc_bytes,
        "validation_warnings": warnings,
        "efficiency_report": efficiency,
        "efficiency_doc_bytes": efficiency_doc_bytes,
        "xml_export_bytes": xml_export_bytes,
    }


def run_xml_import(
    file_path: Path,
    plan_year: int = None,
    org_id: int = 0,
) -> dict:
    """Import Oracle ICM XML export directly into ICM workbook — no LLM needed.

    Parses structured XML to produce oracle_mapping dict, then runs through the
    same transformer / validator / doc-generator pipeline as the LLM path.
    """
    from .parsing import _extract_icm_plan_structured
    from .icm_transformer import (
        transform_analysis_to_icm_workbook,
        write_icm_workbook,
        validate_cross_references,
    )
    from .doc_generator import generate_design_document, generate_config_document

    oracle_mapping = _extract_icm_plan_structured(file_path)

    # Derive OrgId from XML if not explicitly provided by the caller
    if org_id == 0:
        for cp in oracle_mapping.get("compensation_plans", []):
            xml_org_id = cp.get("org_id", 0)
            if xml_org_id and xml_org_id != 0:
                org_id = xml_org_id
                logger.info("Derived OrgId %d from XML compensation plan", org_id)
                break

    # When migrating to a new plan_year, strip original XML dates so
    # infer_oracle_objects fills them with the target year.
    if plan_year is not None:
        for section_key in ("compensation_plans", "plan_components", "performance_measures"):
            for obj in oracle_mapping.get(section_key, []):
                obj.pop("start_date", None)
                obj.pop("end_date", None)

    analysis = {"oracle_mapping": oracle_mapping, "template": "xml_import"}
    analysis = infer_oracle_objects(analysis, org_id=org_id, plan_year=plan_year)

    icm_sheets = transform_analysis_to_icm_workbook(
        analysis, org_id=org_id, plan_year=plan_year,
    )
    warnings = validate_cross_references(icm_sheets)
    workbook_bytes = write_icm_workbook(icm_sheets)

    analysis_id = uuid.uuid4().hex[:12]
    analysis["validation_warnings"] = warnings
    design_doc_bytes = generate_design_document(analysis, analysis_id)
    config_doc_bytes = generate_config_document(analysis, analysis_id)

    # Generate efficiency report for XML imports (past-year analysis)
    from .efficiency_report import analyze_efficiency, generate_efficiency_report_doc
    efficiency = analyze_efficiency(analysis.get("oracle_mapping", {}))
    efficiency_doc_bytes = generate_efficiency_report_doc(efficiency, analysis, analysis_id)

    # Generate XML export for the ensuing year
    from .xml_exporter import generate_icm_xml
    xml_export_bytes = generate_icm_xml(
        analysis.get("oracle_mapping", {}),
        org_id=org_id,
        plan_year=plan_year,
    )

    return {
        "analysis_id": analysis_id,
        "analysis": analysis,
        "icm_workbook_bytes": workbook_bytes,
        "design_doc_bytes": design_doc_bytes,
        "config_doc_bytes": config_doc_bytes,
        "validation_warnings": warnings,
        "efficiency_report": efficiency,
        "efficiency_doc_bytes": efficiency_doc_bytes,
        "xml_export_bytes": xml_export_bytes,
    }
