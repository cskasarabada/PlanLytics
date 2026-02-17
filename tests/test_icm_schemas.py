"""Tests for ICM Pydantic schemas."""
import pytest
from backend.models.icm_schemas import (
    ICMRateDimension,
    ICMRateTable,
    ICMRateTableRate,
    ICMExpression,
    ICMPerformanceMeasure,
    ICMPlanComponent,
    ICMCompensationPlan,
    ICMPerformanceGoal,
    ICMConfigEntry,
    ICMWorkbookData,
)


class TestICMRateDimension:
    def test_required_fields(self):
        rd = ICMRateDimension(rate_dimension_name="Test Dim")
        assert rd.rate_dimension_name == "Test Dim"
        assert rd.rate_dimension_type == "AMOUNT"
        assert rd.org_id == 300000046987012

    def test_custom_values(self):
        rd = ICMRateDimension(
            rate_dimension_name="Revenue Tier",
            rate_dimension_type="AMOUNT",
            org_id=123456,
            tier_sequence=2,
            minimum_amount=50000,
            maximum_amount=100000,
        )
        assert rd.tier_sequence == 2
        assert rd.minimum_amount == 50000


class TestICMCompensationPlan:
    def test_defaults(self):
        cp = ICMCompensationPlan(name="Plan A")
        assert cp.status == "Active"
        assert cp.org_id == 300000046987012
        assert cp.target_incentive == 0.0


class TestICMPlanComponent:
    def test_all_fields(self):
        pc = ICMPlanComponent(
            plan_name="Plan A",
            plan_component_name="Comp 1",
            performance_measure_name="Measure 1",
            rate_table_name="Rate 1",
            incentive_formula_expression="Formula 1",
        )
        assert pc.incentive_type == "Sales"
        assert pc.calculation_method == "Tiered"
        assert pc.earning_basis == "Amount"


class TestICMExpression:
    def test_nullable_fields(self):
        expr = ICMExpression(expression_name="Calc 1")
        assert expr.measure_name is None
        assert expr.constant_value is None
        assert expr.expression_operator is None


class TestICMWorkbookData:
    def test_empty_workbook(self):
        wb = ICMWorkbookData()
        assert wb.rate_dimensions == []
        assert wb.compensation_plans == []

    def test_populated_workbook(self):
        wb = ICMWorkbookData(
            compensation_plans=[ICMCompensationPlan(name="Plan A")],
            rate_dimensions=[ICMRateDimension(rate_dimension_name="Dim 1")],
        )
        assert len(wb.compensation_plans) == 1
        assert len(wb.rate_dimensions) == 1
