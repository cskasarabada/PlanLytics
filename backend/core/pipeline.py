# core/pipeline.py
import json
from pathlib import Path
from .parsing import extract_text
from .prompting import build_prompt, call_llm
from .mapping_oracle import infer_oracle_objects

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
