"""Tests for the ICM transformer — JSON to Excel conversion."""
import pytest
import pandas as pd
from backend.core.icm_transformer import (
    transform_analysis_to_icm_workbook,
    write_icm_workbook,
    validate_cross_references,
    SHEET_COLUMNS,
)


def _sample_oracle_mapping():
    """Return a realistic oracle_mapping that the enhanced AI agent would produce."""
    return {
        "oracle_mapping": {
            "compensation_plans": [{
                "name": "Sales Plan 2025",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "status": "Active",
                "description": "Annual sales commission plan",
                "display_name": "Sales Plan 2025",
                "target_incentive": 100000,
                "org_id": 300000046987012,
            }],
            "plan_components": [{
                "plan_name": "Sales Plan 2025",
                "plan_component_name": "Revenue Component",
                "incentive_type": "Sales",
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "calculation_method": "Tiered",
                "org_id": 300000046987012,
                "performance_measure_name": "Revenue Metric",
                "rate_table_name": "Revenue Rate",
                "rt_start_date": "2025-01-01",
                "rt_end_date": "2025-12-31",
                "incentive_formula_expression": "Revenue Calculation",
                "performance_measure_weight": 1.0,
                "calculation_sequence": 1,
                "earning_basis": "Amount",
            }],
            "rate_dimensions": [
                {"rate_dimension_name": "Revenue Dimension", "rate_dimension_type": "AMOUNT",
                 "org_id": 300000046987012, "tier_sequence": 1,
                 "minimum_amount": 0, "maximum_amount": 50000},
                {"rate_dimension_name": "Revenue Dimension", "rate_dimension_type": "AMOUNT",
                 "org_id": 300000046987012, "tier_sequence": 2,
                 "minimum_amount": 50000, "maximum_amount": 200000},
            ],
            "rate_tables": [{
                "rate_table_name": "Revenue Rate",
                "rate_table_type": "Sales",
                "org_id": 300000046987012,
                "display_name": "Revenue Commission Rate",
            }],
            "rate_table_rates": [
                {"rate_table_name": "Revenue Rate", "minimum_amount": 0,
                 "maximum_amount": 50000, "rate_value": 0.03, "tier_sequence": 1},
                {"rate_table_name": "Revenue Rate", "minimum_amount": 50000,
                 "maximum_amount": 200000, "rate_value": 0.06, "tier_sequence": 2},
            ],
            "expressions": [{
                "expression_name": "Revenue Calculation",
                "expression_id": 1,
                "expression_detail_type": "Calculation",
                "description": "Revenue incentive calculation",
                "expression_type": "Calculation",
                "sequence": 1,
                "measure_name": "Revenue Measure",
                "basic_attributes_group": "Sales",
                "basic_attribute_name": "Revenue",
                "measure_result_attribute": "Revenue Amount",
                "plan_component_name": "Revenue Component",
                "plan_component_result_attribute": "Revenue",
                "constant_value": None,
                "expression_operator": None,
                "expression_detail_id": 1,
            }],
            "performance_measures": [{
                "name": "Revenue Metric",
                "description": "Tracks revenue for incentives",
                "unit_of_measure": "AMOUNT",
                "org_id": 300000046987012,
                "start_date": "2025-01-01",
                "end_date": "2025-12-31",
                "measure_formula_expression_name": "Revenue Calculation",
                "process_transactions": "Yes",
                "performance_interval": "Quarterly",
                "active_flag": "Y",
                "use_external_formula_flag": "N",
                "running_total_flag": "N",
                "f_year": 2025,
                "credit_category_name": "Sales Credit",
            }],
            "performance_goals": [{
                "performance_measure_name": "Revenue Metric",
                "goal_interval": "Quarterly",
                "goal_target": 500000,
            }],
        }
    }


class TestTransformAnalysis:
    def test_produces_all_9_sheets(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        assert set(sheets.keys()) == set(SHEET_COLUMNS.keys())

    def test_sheet_column_names_match(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        for sheet_name, expected_cols in SHEET_COLUMNS.items():
            df = sheets[sheet_name]
            assert list(df.columns) == expected_cols, f"Columns mismatch in {sheet_name}"

    def test_compensation_plans_data(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        df = sheets["Compensation Plans"]
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Sales Plan 2025"
        assert df.iloc[0]["TargetIncentive"] == 100000

    def test_rate_table_rates_data(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        df = sheets["Rate Table Rates"]
        assert len(df) == 2
        assert df.iloc[0]["Rate Value"] == 0.03
        assert df.iloc[1]["Rate Value"] == 0.06

    def test_plan_components_link_to_plan(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        df = sheets["Plan Components"]
        assert df.iloc[0]["PlanName"] == "Sales Plan 2025"
        assert df.iloc[0]["Rate Table Name"] == "Revenue Rate"

    def test_expressions_auto_numbered(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        df = sheets["Expression"]
        assert df.iloc[0]["Sequence"] == 1
        assert df.iloc[0]["Expression ID"] == 1

    def test_config_sheet_has_metadata(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        df = sheets["Config"]
        keys = set(df["Key"])
        assert "Version" in keys
        assert "Year" in keys
        assert "GeneratedBy" in keys

    def test_empty_oracle_mapping(self):
        sheets = transform_analysis_to_icm_workbook({"oracle_mapping": {}})
        for sheet_name in SHEET_COLUMNS:
            assert sheet_name in sheets
        # Data sheets should be empty, Config should have metadata
        assert len(sheets["Compensation Plans"]) == 0
        assert len(sheets["Config"]) > 0


class TestWriteWorkbook:
    def test_produces_bytes(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        wb_bytes = write_icm_workbook(sheets)
        assert isinstance(wb_bytes, bytes)
        assert len(wb_bytes) > 0

    def test_writes_to_file(self, tmp_path):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        out = tmp_path / "test.xlsx"
        write_icm_workbook(sheets, output_path=out)
        assert out.exists()
        # Verify it's a valid Excel file
        xls = pd.ExcelFile(out)
        assert "Compensation Plans" in xls.sheet_names
        assert "Rate Table Rates" in xls.sheet_names


class TestCrossReferenceValidation:
    def test_valid_references_no_warnings(self):
        sheets = transform_analysis_to_icm_workbook(_sample_oracle_mapping())
        warnings = validate_cross_references(sheets)
        assert warnings == []

    def test_missing_plan_reference(self):
        data = _sample_oracle_mapping()
        # Remove compensation plans but keep components referencing them
        data["oracle_mapping"]["compensation_plans"] = []
        sheets = transform_analysis_to_icm_workbook(data)
        warnings = validate_cross_references(sheets)
        assert any("missing plans" in w for w in warnings)

    def test_missing_rate_table_reference(self):
        data = _sample_oracle_mapping()
        data["oracle_mapping"]["rate_tables"] = []
        sheets = transform_analysis_to_icm_workbook(data)
        warnings = validate_cross_references(sheets)
        assert any("missing rate tables" in w for w in warnings)
