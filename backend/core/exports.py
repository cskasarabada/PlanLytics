# core/exports.py
import pandas as pd
from pathlib import Path

def to_excel(analysis: dict, outpath: Path):
    with pd.ExcelWriter(outpath) as xw:
        pd.DataFrame(analysis.get("plan_structure",[])).to_excel(xw, "PlanStructure", index=False)
        pd.DataFrame(analysis.get("risks",[])).to_excel(xw, "Risks", index=False)
        pd.DataFrame(analysis.get("oracle_mapping",{}).get("transactions",[])).to_excel(xw, "Transactions", index=False)
        pd.DataFrame(analysis.get("side_by_side_rows",[])).to_excel(xw, "SideBySide", index=False)
        pd.DataFrame(analysis.get("vendor_compare_rows",[])).to_excel(xw, "VendorCompare", index=False)

def simple_html_summary(analysis: dict) -> str:
    risks = "".join(f"<li><b>{r.get('title')}</b> – {r.get('severity')}: {r.get('detail')}</li>" for r in analysis.get("risks",[]))
    return f"""
    <h2>ICM Automation Analysis – {analysis.get('template')}</h2>
    <h3>Risks</h3><ul>{risks}</ul>
    """

def to_icm_excel(analysis: dict, outpath: Path, org_id: int = 0):
    """Export analysis as ICM Optimizer-compatible Excel workbook."""
    from .icm_transformer import transform_analysis_to_icm_workbook, write_icm_workbook
    sheets = transform_analysis_to_icm_workbook(analysis, org_id=org_id)
    write_icm_workbook(sheets, output_path=outpath)


def to_pdf(html_str: str, outpath: Path):
    # Skip real PDF for now to avoid system deps; write HTML as .html alongside
    Path(outpath.with_suffix(".html")).write_text(html_str, encoding="utf-8")
