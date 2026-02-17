# core/parsing.py
from pathlib import Path
import docx
from pypdf import PdfReader


def extract_text(path: Path) -> str:
    sfx = path.suffix.lower()
    if sfx == ".docx":
        d = docx.Document(str(path))
        return "\n".join(p.text for p in d.paragraphs if p.text.strip())
    if sfx == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if sfx == ".xml":
        return _extract_icm_plan_xml(path)
    return Path(path).read_text(errors="ignore")


def _extract_icm_plan_xml(path: Path) -> str:
    """Extract a readable plan summary from Oracle ICM IcCnPlanCopy XML export.

    Converts the structured XML into natural-language text that the LLM prompt
    can consume, preserving plan names, components, expressions, rate tables,
    goals, and credit categories.
    """
    import xml.etree.ElementTree as ET

    tree = ET.parse(str(path))
    root = tree.getroot()
    lines = []

    # Check if this is an IcCnPlanCopy export
    if root.tag == "IcCnPlanCopy":
        lines.append("Oracle ICM Plan Export")
        lines.append(f"Exported: {root.get('Date', 'N/A')}")
        lines.append(f"Server: {root.get('ServerURI', 'N/A')}")
        lines.append(f"User: {root.get('User', 'N/A')}")
        lines.append("")

    for plan_obj in root.iter("PlanObjects"):
        for comp_plan in plan_obj.iter("CompPlan"):
            plan_name = comp_plan.get("Name", "Unknown Plan")
            lines.append(f"Compensation Plan: {plan_name}")
            lines.append(f"  Business Unit: {comp_plan.get('BusinessUnit', '')}")
            lines.append(f"  OrgId: {comp_plan.get('OrgId', '')}")
            lines.append(f"  Start Date: {comp_plan.get('StartDate', '')}")
            lines.append(f"  End Date: {comp_plan.get('EndDate', '')}")

            # CompPlansVORow details
            for row in comp_plan.iter("CompPlansVORow"):
                lines.append(f"  Approval Status: {_xml_text(row, 'ApprovalStatus')}")
                lines.append(f"  Plan Status: {_xml_text(row, 'PlanStatus')}")
                lines.append(f"  Target Incentive: {_xml_text(row, 'TargetIncentive')}")
                lines.append(f"  Allow Credit Category Overlap: {_xml_text(row, 'AllowEcatOverlapFlag')}")
                lines.append(f"  Display Name: {_xml_text(row, 'DisplayName')}")
                lines.append(f"  Plan Document Template: {_xml_text(row, 'PlanDocTemplate')}")
            lines.append("")

            # Plan Components
            for pc in comp_plan.iter("PlanComponent"):
                pc_name = pc.get("Name", "")
                pc_type = pc.get("IncentiveType", "")
                lines.append(f"  Plan Component: {pc_name}")
                lines.append(f"    Incentive Type: {pc_type}")
                lines.append(f"    Start Date: {pc.get('StartDate', '')}")
                lines.append(f"    End Date: {pc.get('EndDate', '')}")

                for pc_row in pc.iter("PlanComponentsVORow"):
                    lines.append(f"    Calculation Phase: {_xml_text(pc_row, 'CalculationPhase')}")
                    lines.append(f"    Indirect Credit: {_xml_text(pc_row, 'IndirectCredit')}")
                    lines.append(f"    Payment Group: {_xml_text(pc_row, 'PaymentGroupCode')}")
                    lines.append(f"    Report Group: {_xml_text(pc_row, 'ReportGroup')}")

                # Formulas (measures and incentive formulas)
                for formula in pc.iter("Formula"):
                    f_name = formula.get("Name", "")
                    f_type = formula.get("Type", "")
                    lines.append(f"    Formula: {f_name} (Type: {f_type})")
                    lines.append(f"      Process Transaction: {formula.get('ProcessTransaction', '')}")
                    lines.append(f"      Accumulation Interval: {formula.get('AccumulationInterval', '')}")

                    # Expressions
                    for expr in formula.iter("Expression"):
                        expr_name = expr.get("Name", "")
                        lines.append(f"      Expression: {expr_name}")
                        for expr_row in expr.iter("ExpressionsVORow"):
                            rendered = _xml_text(expr_row, "RenderedExpressionDisp")
                            if rendered:
                                lines.append(f"        Formula: {rendered}")
                            status = _xml_text(expr_row, "StatusCode")
                            if status:
                                lines.append(f"        Status: {status}")
                            uses_rt = _xml_text(expr_row, "UsesRatetblRsltFlag")
                            if uses_rt == "Y":
                                lines.append("        Uses Rate Table Result: Yes")

                        # Expression details
                        for detail in expr.iter("ExpressionDetail"):
                            table = detail.get("TableName", "")
                            col = detail.get("ColumnName", "")
                            measure = detail.get("MeasureName", "")
                            if table or col:
                                lines.append(f"        Detail: {table}.{col}")
                            if measure:
                                lines.append(f"        Measure Reference: {measure}")

                    # Goals
                    for goal in formula.iter("GoalsVORow"):
                        g_name = _xml_text(goal, "GoalName")
                        g_target = _xml_text(goal, "Target")
                        g_uom = _xml_text(goal, "UnitOfMeasure")
                        lines.append(f"      Goal: {g_name} (Target: {g_target}, Unit: {g_uom})")

                    # Formula details
                    for f_row in formula.iter("FormulasVORow"):
                        split = _xml_text(f_row, "SplitOption")
                        accum = _xml_text(f_row, "AccumulationFlag")
                        process = _xml_text(f_row, "ProcessTxn")
                        if split and split != "NONE":
                            lines.append(f"      Split Option: {split}")
                        if accum:
                            lines.append(f"      Accumulation: {accum}")
                        if process:
                            lines.append(f"      Process Transactions: {process}")

                    # Rate Tables
                    for rt in formula.iter("RateTable"):
                        rt_name = rt.get("Name", "")
                        rt_type = rt.get("Type", "")
                        lines.append(f"      Rate Table: {rt_name} (Type: {rt_type})")

                        for dim in rt.iter("RateDimension"):
                            dim_name = dim.get("Name", "")
                            dim_type = dim.get("Type", "")
                            lines.append(f"        Rate Dimension: {dim_name} (Type: {dim_type})")
                            for tier in dim.iter("RateDimTierVORow"):
                                seq = _xml_text(tier, "TierSequence")
                                min_a = _xml_text(tier, "MinimumAmount")
                                max_a = _xml_text(tier, "MaximumAmount")
                                lines.append(f"          Tier {seq}: {min_a} - {max_a}")

                        for rv in rt.iter("RateTableValueVORow"):
                            seq = _xml_text(rv, "RateSequence")
                            val = _xml_text(rv, "CommissionValue")
                            lines.append(f"        Rate Tier {seq}: {val}")

                    # Formula input expressions (rate dimension input)
                    for fi in formula.iter("FormulaInputExpsVORow"):
                        fi_name = _xml_text(fi, "ExpressionName")
                        fi_split = _xml_text(fi, "SplitFlag")
                        lines.append(f"      Rate Dimension Input: {fi_name} (Split: {fi_split})")

                # Eligible categories (credit categories)
                for ecat in pc.iter("EligibleCat"):
                    lines.append(f"    Credit Category: {ecat.get('Name', '')}")

                lines.append("")

            # Comp plan component links
            for cpc in comp_plan.iter("CompPlanComponentsVORow"):
                pc_name = _xml_text(cpc, "PlanComponentName")
                seq = _xml_text(cpc, "CalculationSequence")
                weight = _xml_text(cpc, "TargetIncentiveWeight")
                phase = _xml_text(cpc, "CalculationPhase")
                lines.append(f"  Plan-Component Link: {pc_name}")
                lines.append(f"    Sequence: {seq}, Weight: {weight}%, Phase: {phase}")
                lines.append(f"    Indirect Credit: {_xml_text(cpc, 'IndirectCredit')}")

    return "\n".join(lines)


def _xml_text(element, tag: str) -> str:
    """Safely extract text from an XML sub-element."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


# ---------------------------------------------------------------------------
# Structured XML import — produces oracle_mapping dict directly (no LLM)
# ---------------------------------------------------------------------------

def _extract_icm_plan_structured(path: Path) -> dict:
    """Parse Oracle ICM IcCnPlanCopy XML into an oracle_mapping dict.

    Returns a dict with the same 11 sections that the LLM-based pipeline produces,
    ready to feed into ``infer_oracle_objects()`` and ``transform_analysis_to_icm_workbook()``.
    """
    import xml.etree.ElementTree as ET
    import re

    tree = ET.parse(str(path))
    root = tree.getroot()

    compensation_plans = []
    plan_components = []
    performance_measures = []
    expressions = []
    performance_goals = []
    rate_tables = []
    rate_dimensions = []
    rate_table_rates = []
    credit_categories_set: dict = {}  # name → dict (dedup)
    calculation_settings = []
    scorecards = []

    seen_expressions: set = set()  # deduplicate by name
    expr_seq = 0

    def _infer_expression_category(usage_code: str, rendered: str) -> str:
        """Infer expression category from XML UsageCode or rendered text."""
        if usage_code:
            uc = usage_code.upper()
            if uc.startswith("MEASURE_"):
                return "Attainment"
            if "INCENTIVE_FORM" in uc:
                return "Earnings"
        if "Credit.Credit Amount" in rendered:
            return "Attainment"
        if "result" in rendered.lower():
            return "Earnings"
        return "Earnings"

    def _parse_rendered_expression(rendered: str, expr_name: str, category: str):
        """Parse rendered expression text into expression detail rows.

        Returns a list of expression detail dicts matching the Expression sheet schema.
        """
        nonlocal expr_seq
        if not rendered:
            return []

        rows = []
        # Tokenize: split on whitespace but keep parentheses as tokens
        tokens = re.findall(r'[()]|[^\s()]+', rendered)
        # Group tokens into semantic parts
        i = 0
        while i < len(tokens):
            token = tokens[i]
            # Skip parentheses (SUM ( ... ) — the function is part of expression type)
            if token in ("(", ")", "SUM", "COUNT", "MIN", "MAX", "AVG"):
                i += 1
                continue

            expr_seq += 1

            # Math operator
            if token in ("+", "-", "*", "/"):
                rows.append({
                    "expression_name": expr_name,
                    "expression_id": expr_seq,
                    "expression_detail_type": "Math operator",
                    "description": expr_name,
                    "expression_type": "Calculation",
                    "expression_category": category,
                    "sequence": expr_seq,
                    "expression_operator": token,
                    "expression_detail_id": expr_seq,
                })
                i += 1
                continue

            # "Credit.Credit Amount" pattern
            if token.startswith("Credit."):
                attr_name = token.split(".", 1)[1] if "." in token else token
                rows.append({
                    "expression_name": expr_name,
                    "expression_id": expr_seq,
                    "expression_detail_type": "Primary object attribute",
                    "description": expr_name,
                    "expression_type": "Calculation",
                    "expression_category": category,
                    "sequence": expr_seq,
                    "basic_attributes_group": "Credit",
                    "basic_attribute_name": attr_name,
                    "expression_detail_id": expr_seq,
                })
                i += 1
                continue

            # "Measure result.X.PTD Output Achieved" pattern
            if token == "Measure" and i + 1 < len(tokens) and tokens[i + 1].startswith("result."):
                # Reassemble: "Measure result.NAME.ATTRIBUTE"
                full = "Measure " + tokens[i + 1]
                # Could span multiple tokens if measure name has spaces
                j = i + 2
                while j < len(tokens) and tokens[j] not in ("+", "-", "*", "/", "(", ")"):
                    full += " " + tokens[j]
                    j += 1
                # Parse: "Measure result.MEASURE_NAME.RESULT_ATTR"
                parts = full.split(".")
                measure_name = parts[1] if len(parts) > 1 else ""
                result_attr = parts[2] if len(parts) > 2 else "PTD Output Achieved"
                rows.append({
                    "expression_name": expr_name,
                    "expression_id": expr_seq,
                    "expression_detail_type": "Measure result",
                    "description": expr_name,
                    "expression_type": "Calculation",
                    "expression_category": category,
                    "sequence": expr_seq,
                    "measure_name": measure_name,
                    "measure_result_attribute": result_attr,
                    "expression_detail_id": expr_seq,
                })
                i = j
                continue

            # "Plan component result.X.PTD Output Achieved" pattern
            if token == "Plan" and i + 2 < len(tokens) and tokens[i + 1] == "component" and tokens[i + 2].startswith("result."):
                full = "Plan component " + tokens[i + 2]
                j = i + 3
                while j < len(tokens) and tokens[j] not in ("+", "-", "*", "/", "(", ")"):
                    full += " " + tokens[j]
                    j += 1
                parts = full.split(".")
                pc_name = parts[1] if len(parts) > 1 else ""
                pc_attr = parts[2] if len(parts) > 2 else "PTD Output Achieved"
                rows.append({
                    "expression_name": expr_name,
                    "expression_id": expr_seq,
                    "expression_detail_type": "Plan component result",
                    "description": expr_name,
                    "expression_type": "Calculation",
                    "expression_category": category,
                    "sequence": expr_seq,
                    "plan_component_name": pc_name,
                    "plan_component_result_attribute": pc_attr,
                    "expression_detail_id": expr_seq,
                })
                i = j
                continue

            # Numeric constant
            try:
                float(token)
                rows.append({
                    "expression_name": expr_name,
                    "expression_id": expr_seq,
                    "expression_detail_type": "Constant",
                    "description": expr_name,
                    "expression_type": "Calculation",
                    "expression_category": category,
                    "sequence": expr_seq,
                    "constant_value": token,
                    "expression_detail_id": expr_seq,
                })
                i += 1
                continue
            except ValueError:
                pass

            # Unknown token — skip
            i += 1

        return rows

    # ---- Main traversal ----
    for plan_obj in root.iter("PlanObjects"):
        for comp_plan in plan_obj.iter("CompPlan"):
            plan_name = comp_plan.get("Name", "Unknown Plan")
            org_id_str = comp_plan.get("OrgId", "0")

            # CompPlansVORow for extra details
            cp_row = comp_plan.find("CompPlansVORow")
            display_name = _xml_text(cp_row, "DisplayName") if cp_row is not None else plan_name
            target_incentive = 0
            try:
                target_incentive = float(_xml_text(cp_row, "TargetIncentive")) if cp_row is not None else 0
            except (ValueError, TypeError):
                pass

            compensation_plans.append({
                "name": plan_name,
                "start_date": comp_plan.get("StartDate", ""),
                "end_date": comp_plan.get("EndDate", ""),
                "org_id": int(org_id_str) if org_id_str.isdigit() else 0,
                "display_name": display_name,
                "target_incentive": target_incentive,
                "description": plan_name,
                "status": "Active",
            })

            # -- Plan Components --
            for pc_elem in comp_plan.iter("PlanComponent"):
                pc_name = pc_elem.get("Name", "")
                pc_type = pc_elem.get("IncentiveType", "BONUS")

                pc_row = pc_elem.find("PlanComponentsVORow")
                indirect_credit = _xml_text(pc_row, "IndirectCredit") if pc_row is not None else "NONE"
                calc_phase = _xml_text(pc_row, "CalculationPhase") if pc_row is not None else "1"

                # Collect credit categories for this component
                component_credit_cats = []
                for ecat in pc_elem.iter("EligibleCat"):
                    cat_name = ecat.get("Name", "")
                    if cat_name:
                        component_credit_cats.append(cat_name)
                        if cat_name not in credit_categories_set:
                            credit_categories_set[cat_name] = {
                                "credit_category_name": cat_name,
                                "description": cat_name,
                                "action": "reuse",
                            }

                # Track measure formula expression and rate table per component
                measure_expr_name = ""
                incentive_expr_name = ""
                rate_table_name_for_pc = ""
                rate_dim_input_expr = ""

                for formula in pc_elem.iter("Formula"):
                    f_name = formula.get("Name", "")
                    f_type = formula.get("Type", "")  # MEASURE or INCENTIVE_FORMULA
                    process_txn = formula.get("ProcessTransaction", "GROUP")
                    accum_interval = formula.get("AccumulationInterval", "Period")

                    # -- Expressions inside this formula --
                    for expr_elem in formula.iter("Expression"):
                        expr_name = expr_elem.get("Name", "")
                        if not expr_name or expr_name in seen_expressions:
                            continue

                        expr_vo = expr_elem.find("ExpressionsVORow")
                        rendered = _xml_text(expr_vo, "RenderedExpressionDisp") if expr_vo is not None else ""

                        # Determine category from usage codes
                        usage_code = ""
                        usages_parent = expr_vo.find("ExpressionUsages") if expr_vo is not None else None
                        if usages_parent is not None:
                            first_usage = usages_parent.find("ExpressionUsagesVORow")
                            if first_usage is not None:
                                usage_code = _xml_text(first_usage, "UsageCode")

                        category = _infer_expression_category(usage_code, rendered)

                        # Parse rendered expression into detail rows
                        detail_rows = _parse_rendered_expression(rendered, expr_name, category)
                        if detail_rows:
                            expressions.extend(detail_rows)
                        else:
                            # Fallback: single expression row with rendered text as description
                            expr_seq += 1
                            expressions.append({
                                "expression_name": expr_name,
                                "expression_id": expr_seq,
                                "expression_detail_type": "Calculation",
                                "description": rendered or expr_name,
                                "expression_type": "Calculation",
                                "expression_category": category,
                                "sequence": expr_seq,
                                "expression_detail_id": expr_seq,
                            })

                        seen_expressions.add(expr_name)

                        # Track which expression is the measure formula vs incentive formula
                        if f_type == "MEASURE":
                            measure_expr_name = expr_name
                        elif f_type == "INCENTIVE_FORMULA":
                            incentive_expr_name = expr_name

                    # -- Performance Measure (from MEASURE formulas) --
                    if f_type == "MEASURE":
                        # Goals
                        for goal_row in formula.iter("GoalsVORow"):
                            g_name = _xml_text(goal_row, "GoalName")
                            g_target = _xml_text(goal_row, "Target") or "0"
                            g_uom = _xml_text(goal_row, "UnitOfMeasure") or "AMOUNT"
                            if g_name:
                                performance_goals.append({
                                    "performance_measure_name": g_name,
                                    "goal_interval": _interval_to_goal(accum_interval),
                                    "goal_target": float(g_target) if g_target else 0,
                                })

                        first_cat = component_credit_cats[0] if component_credit_cats else ""
                        performance_measures.append({
                            "name": f_name,
                            "description": f_name,
                            "unit_of_measure": "AMOUNT",
                            "process_transactions": "Yes" if process_txn == "GROUP" else "No",
                            "performance_interval": _interval_to_goal(accum_interval),
                            "measure_formula_expression_name": measure_expr_name,
                            "credit_category_name": first_cat,
                        })

                    # -- Rate Tables (from INCENTIVE_FORMULA formulas) --
                    if f_type == "INCENTIVE_FORMULA":
                        for rt_elem in formula.iter("RateTable"):
                            rt_name = rt_elem.get("Name", "")
                            rt_type = rt_elem.get("Type", "AMOUNT")
                            if rt_name:
                                rate_table_name_for_pc = rt_name
                                # Only add if not already seen
                                if not any(r["rate_table_name"] == rt_name for r in rate_tables):
                                    rate_tables.append({
                                        "rate_table_name": rt_name,
                                        "rate_table_type": rt_type,
                                        "display_name": rt_name,
                                    })

                                # Rate dimensions and tiers
                                for dim_elem in rt_elem.iter("RateDimension"):
                                    dim_name = dim_elem.get("Name", "")
                                    dim_type = dim_elem.get("Type", "AMOUNT")
                                    for tier_row in dim_elem.iter("RateDimTierVORow"):
                                        seq = _xml_text(tier_row, "TierSequence")
                                        min_a = _xml_text(tier_row, "MinimumAmount")
                                        max_a = _xml_text(tier_row, "MaximumAmount")
                                        rate_dimensions.append({
                                            "rate_dimension_name": dim_name,
                                            "rate_dimension_type": dim_type,
                                            "tier_sequence": int(seq) if seq else 1,
                                            "minimum_amount": float(min_a) if min_a else 0,
                                            "maximum_amount": float(max_a) if max_a else 999999,
                                        })

                                # Rate table values
                                for rv_row in rt_elem.iter("RateTableValueVORow"):
                                    r_seq = _xml_text(rv_row, "RateSequence")
                                    r_val = _xml_text(rv_row, "CommissionValue")
                                    r_min = _xml_text(rv_row, "MinimumAmount")
                                    r_max = _xml_text(rv_row, "MaximumAmount")
                                    rate_table_rates.append({
                                        "rate_table_name": rt_name,
                                        "tier_sequence": int(r_seq) if r_seq else 1,
                                        "rate_value": float(r_val) if r_val else 0.0,
                                        "minimum_amount": float(r_min) if r_min else 0,
                                        "maximum_amount": float(r_max) if r_max else 999999,
                                    })

                        # Rate dimension input expression
                        for fi_row in formula.iter("FormulaInputExpsVORow"):
                            fi_name = _xml_text(fi_row, "ExpressionName")
                            if fi_name:
                                rate_dim_input_expr = fi_name

                # Build plan component
                plan_components.append({
                    "plan_name": plan_name,
                    "plan_component_name": pc_name,
                    "incentive_type": pc_type,
                    "performance_measure_name": pc_name,  # measure has same name as component
                    "rate_table_name": rate_table_name_for_pc,
                    "incentive_formula_expression": incentive_expr_name,
                    "calculation_method": "Tiered" if rate_table_name_for_pc else "Flat",
                    "include_indirect_credits": indirect_credit if indirect_credit != "NONE" else "None",
                    "rate_dimension_input_expression": rate_dim_input_expr or None,
                })

                # Calculation settings
                calculation_settings.append({
                    "plan_component_name": pc_name,
                    "process_transactions": "Grouped by interval",
                })

    return {
        "compensation_plans": compensation_plans,
        "plan_components": plan_components,
        "performance_measures": performance_measures,
        "expressions": expressions,
        "performance_goals": performance_goals,
        "rate_tables": rate_tables,
        "rate_dimensions": rate_dimensions,
        "rate_table_rates": rate_table_rates,
        "credit_categories": list(credit_categories_set.values()),
        "calculation_settings": calculation_settings,
        "scorecards": scorecards,
    }


def _interval_to_goal(accum_interval: str) -> str:
    """Convert XML AccumulationInterval to GoalInterval string."""
    mapping = {
        "Period": "Period",
        "Quarter": "Quarterly",
        "Year": "Yearly",
        "Cumulative": "Cumulative",
    }
    return mapping.get(accum_interval, "Period")
