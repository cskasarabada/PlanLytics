"""
Plan Component Manager for Oracle ICM Plan Configuration Optimizer.
Handles creation and configuration of Plan Components.
"""

import os
import logging
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from .perf_measure import PerformanceMeasureManager
from ..utils.logging_utils import log_api_response

class PlanComponentManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None, performance_measure_manager: Optional[PerformanceMeasureManager] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file
        self.excel_path = excel_path
        self.performance_measure_manager = performance_measure_manager
        self.logger = logging.getLogger(__name__)

        # Define the plan component endpoint for Oracle ICM API
        self.plan_component_endpoint = "/fscmRestApi/resources/11.13.18.05/planComponents"  # Updated endpoint

        # Retrieve org_id from the organization section
        organization_section = self.config_manager.get('organization') or {}
        self.org_id = organization_section.get('org_id', None)
        if not self.org_id:
            self.logger.error("No org_id found in configuration")
            raise ValueError("No org_id found in configuration")

        # Validate Excel file if provided
        if self.excel_path and not self._validate_excel_file():
            error_msg = f"Excel file not found: {self.excel_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

    def _validate_excel_file(self) -> bool:
        """Validate if the Excel file exists and is accessible."""
        if not self.excel_path:
            self.logger.error("Excel file path is empty")
            return False
        if not os.path.exists(self.excel_path):
            self.logger.error(f"Excel file not found: {self.excel_path}")
            return False
        if not os.access(self.excel_path, os.R_OK):
            self.logger.error(f"Excel file not readable: {self.excel_path}")
            return False
        return True

    def load_plan_components(self) -> List[Dict[str, Any]]:
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Plan Components', dtype=str)
            df = df.where(pd.notnull(df), None)
            required_columns = ['Plan Component Name', 'Start Date', 'End Date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"❌ Missing required columns in 'Plan Components' sheet: {missing_columns}")
                return []
            plan_components = df.to_dict('records')
            return [pc for pc in plan_components if pc['Plan Component Name']]
        except Exception as e:
            self.logger.exception(f"❌ Error loading Plan Components from Excel: {e}")
            return []

    def get_plan_component_id(self, name: str) -> Optional[Tuple[int, int, str]]:
        self.logger.info(f"🔍 Retrieving Plan Component details for: {name}")
        endpoint = f"{self.plan_component_endpoint}?q=Name='{quote(name)}';OrgId={self.org_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Plan Component by Name: {name}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            plan_component = response["items"][0]
            plan_component_id = plan_component.get("PlanComponentId")
            plan_components_uniq_id = None
            incentive_formula_id = None
            for link in plan_component.get("links", []):
                if link.get("rel") == "self":
                    plan_components_uniq_id = link.get("href").split("/")[-1]
                    break
            if not plan_components_uniq_id:
                self.logger.error(f"❌ Could not retrieve planComponentsUniqID for '{name}'.")
                return None, None, None
            endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas"
            response, status_code = self.api_client.get(endpoint)
            if status_code == 200 and response.get("items"):
                incentive_formula = response["items"][0]
                incentive_formula_id = incentive_formula.get("IncentiveFormulaId")
            self.logger.info(f"✅ Found Plan Component ID: {plan_component_id}, IncentiveFormulaId: {incentive_formula_id}, planComponentsUniqID: {plan_components_uniq_id}, and formulas endpoint")
            return plan_component_id, incentive_formula_id, plan_components_uniq_id
        self.logger.warning(f"⚠ Plan Component '{name}' not found.")
        return None, None, None

    def create_plan_component(self, name: str, start_date: str, end_date: str, description: str = None,
                               incentive_type: str = "COMMISSION", calculation_phase: int = 1,
                               earning_type: int = -1000, calculate_incentive: str = "COMMISSION") -> Optional[Tuple[int, int, str]]:
        """Create a Plan Component in Oracle ICM.

        Oracle planComponents POST payload field types (from API schema + example):
          - Name (string)
          - OrgId (integer)
          - StartDate / EndDate (string, YYYY-MM-DD)
          - Description (string)
          - IncentiveType (string lookup: BONUS, COMMISSION, STANDARD) — CN_REPORT_GROUP
          - CalculateIncentive (string lookup: BONUS, COMMISSION) — CN_PLAN_INCENTIVE_TYPE
          - EarningType (integer: -1000 = Monetary earnings) — EarningTypesVO
          - CalculationPhase (integer: 1 = Phase 1, 2 = Phase 2) — CN_CALCULATION_PHASE
          - PaymentPlanCategory (string lookup: STANDARD) — CN_PAYMENT_PLAN_CATEGORY
          - DisplayName (string)
          - ValidForCalculation is READ-ONLY (auto-set to INCOMPLETE by Oracle)
        """
        endpoint = f"{self.plan_component_endpoint}"
        payload = {
            "Name": name,
            "OrgId": self.org_id,
            "StartDate": start_date,
            "EndDate": end_date,
            "Description": description if description else name,
            "IncentiveType": incentive_type,
            "CalculateIncentive": calculate_incentive,
            "EarningType": earning_type,
            "CalculationPhase": calculation_phase,
            "PaymentPlanCategory": "STANDARD",
            "DisplayName": name
        }
        response, status_code = self.api_client.post(endpoint, payload)
        log_api_response(f"Create Plan Component: {name}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code in [200, 201]:
            plan_component_id = response.get("PlanComponentId")
            plan_components_uniq_id = None
            incentive_formula_id = None
            for link in response.get("links", []):
                if link.get("rel") == "self":
                    plan_components_uniq_id = link.get("href").split("/")[-1]
                    break
            if not plan_components_uniq_id:
                self.logger.error(f"❌ Could not retrieve planComponentsUniqID for newly created Plan Component '{name}'.")
                return None, None, None
            endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas"
            response, status_code = self.api_client.get(endpoint)
            if status_code == 200 and response.get("items"):
                incentive_formula = response["items"][0]
                incentive_formula_id = incentive_formula.get("IncentiveFormulaId")
            return plan_component_id, incentive_formula_id, plan_components_uniq_id
        # If creation failed (e.g., 400 "already exists"), try to fetch the existing one
        if status_code == 400:
            self.logger.warning(f"⚠ POST returned 400 for Plan Component '{name}'. Checking if it already exists.")
            existing = self.get_plan_component_id(name)
            if existing and existing[0]:
                self.logger.info(f"✅ Found existing Plan Component '{name}' with ID: {existing[0]}")
                return existing
        self.logger.error(f"❌ Failed to create Plan Component '{name}'. Status: {status_code}, Response: {response}")
        return None, None, None

    def _check_expression_status(self, expression_name: str) -> Optional[str]:
        """Check expression Status by fetching it from Oracle.

        Returns the Status string ('VALID', 'INVALID', etc.) or None if not found.
        """
        try:
            endpoint = f"{self.plan_component_endpoint.replace('planComponents', 'incentiveCompensationExpressions')}?q=Name='{quote(expression_name)}'"
            response, status_code = self.api_client.get(endpoint)
            if status_code == 200 and response.get("items"):
                status = response["items"][0].get("Status", "INVALID")
                self.logger.info(f"🔍 Expression '{expression_name}' Status: {status}")
                return status
            return None
        except Exception as e:
            self.logger.warning(f"⚠ Could not check expression status: {e}")
            return None

    def get_expression_id(self, expression_name: str) -> Optional[Tuple[int, int]]:
        self.logger.info(f"🔍 Retrieving Expression ID for: {expression_name}")
        try:
            endpoint = f"{self.plan_component_endpoint.replace('planComponents', 'incentiveCompensationExpressions')}?q=Name='{quote(expression_name)}'"
            response, status_code = self.api_client.get(endpoint)
            if status_code != 200 or not response.get("items"):
                self.logger.error(f"❌ Expression '{expression_name}' not found. Status: {status_code}")
                return None

            expression = response["items"][0]
            expression_id = expression.get("ExpressionId")
            org_id = expression.get("OrgId")
            if expression_id:
                self.logger.info(f"✅ Found Expression '{expression_name}' ID: {expression_id}, OrgId: {org_id}")
                return expression_id, org_id

            self.logger.error(f"❌ Expression '{expression_name}' found but has no ExpressionId.")
            return None
        except Exception as e:
            self.logger.exception(f"❌ Error retrieving Expression ID: {e}")
            return None

    def assign_expression_to_incentive_formula(self, plan_component_id: int, incentive_formula_id: int, expression_id: int, plan_components_uniq_id: str) -> Tuple[Any, int]:
        """Assign an expression to a Plan Component's Incentive Formula via PATCH.

        Oracle PATCH field: IncentiveFormulaExpressionId (maps internally to OutputExpId).
        The expression MUST have Status=VALID before assignment — otherwise Oracle
        returns 400 "The value of the attribute OutputExpId isn't valid".
        """
        endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}"
        payload = {
            "IncentiveFormulaExpressionId": expression_id
        }
        return self.api_client.patch(endpoint, payload)

    def get_rate_table_id(self, rate_table_name: str) -> Optional[int]:
        self.logger.info(f"🔍 Retrieving Rate Table ID for: {rate_table_name}")
        endpoint = f"{self.plan_component_endpoint.replace('planComponents', 'rateTables')}?q=Name='{quote(rate_table_name)}';OrgId={self.org_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Rate Table by Name: {rate_table_name}, OrgId: {self.org_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            rate_table = response["items"][0]
            rate_table_id = rate_table.get("RateTableId")
            self.logger.info(f"✅ Found Rate Table ID: {rate_table_id}")
            return rate_table_id
        self.logger.error(f"❌ Rate Table '{rate_table_name}' not found.")
        return None

    def get_existing_rate_table_assignment(self, plan_components_uniq_id: str, incentive_formula_id: int, rate_table_id: int) -> Optional[str]:
        self.logger.info(f"🔍 Checking existing Rate Table assignment for RateTableId {rate_table_id} to Incentive Formula ID {incentive_formula_id}")
        endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}/child/planComponentRateTables?q=RateTableId={rate_table_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Existing Rate Table Assignment for Incentive Formula ID {incentive_formula_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            rate_table_assignment = response["items"][0]
            rate_dimensional_inputs_endpoint = None
            for link in rate_table_assignment.get("links", []):
                if link.get("name") == "planComponentRateDimensionalInputs":
                    rate_dimensional_inputs_endpoint = link.get("href")
                    break
            if rate_dimensional_inputs_endpoint:
                self.logger.info(f"✅ Found existing Rate Table assignment with RateDimensionalInputs endpoint")
                return rate_dimensional_inputs_endpoint
            else:
                self.logger.info(f"⚠ Rate Table ID {rate_table_id} assigned but no RateDimensionalInputs endpoint found.")
                return None
        return None

    def get_rate_table_details(self, rate_table_id: int) -> Optional[Dict[str, Any]]:
        self.logger.info(f"🔍 Retrieving Rate Table details for ID: {rate_table_id}")
        endpoint = f"{self.plan_component_endpoint.replace('planComponents', 'rateTables')}/{rate_table_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Rate Table details for ID {rate_table_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200:
            self.logger.info(f"✅ Retrieved Rate Table details for ID {rate_table_id}")
            return response
        self.logger.error(f"❌ Failed to retrieve Rate Table details for ID {rate_table_id}. Status: {status_code}")
        return None

    def assign_rate_table_to_incentive_formula(self, plan_component_id: int, incentive_formula_id: int, rate_table_name: str, start_date: str, end_date: str, plan_components_uniq_id: str) -> Optional[str]:
        self.logger.info(f"🔧 Assigning Rate Table '{rate_table_name}' to Incentive Formula ID {incentive_formula_id}")
        try:
            rate_table_id = self.get_rate_table_id(rate_table_name)
            if not rate_table_id:
                self.logger.error(f"❌ Could not find Rate Table ID for '{rate_table_name}'. Assignment failed.")
                return None
            self.logger.debug(f"Rate Table ID for '{rate_table_name}': {rate_table_id}")

            # Check if Rate Table is already assigned with matching dates
            endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}/child/planComponentRateTables?q=RateTableId={rate_table_id}"
            response, status_code = self.api_client.get(endpoint)
            if status_code == 200 and response.get("items"):
                existing_assignment = response["items"][0]
                existing_start_date = existing_assignment["StartDate"]
                existing_end_date = existing_assignment["EndDate"]
                if existing_start_date == start_date and existing_end_date == end_date:
                    self.logger.info(f"✅ Rate Table '{rate_table_name}' already assigned with matching dates ({start_date} to {end_date}). Reusing existing assignment.")
                    plan_component_rate_table_id = existing_assignment["PlanComponentRateTableId"]
                    rate_dimensional_inputs_endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}/child/planComponentRateTables/{plan_component_rate_table_id}/child/planComponentRateDimensionalInputs"
                    self.logger.debug(f"Constructed RateDimensionalInputs endpoint: {rate_dimensional_inputs_endpoint}")
                    return rate_dimensional_inputs_endpoint

            # Proceed with new assignment if no matching existing assignment
            rate_table_details = self.get_rate_table_details(rate_table_id)
            if not rate_table_details:
                self.logger.error(f"❌ Could not retrieve Rate Table details for '{rate_table_name}'. Assignment failed.")
                return None

            rate_dimensions_endpoint = None
            for link in rate_table_details.get("links", []):
                if link.get("name") == "rateDimensions":
                    rate_dimensions_endpoint = link.get("href")
                    break
            if not rate_dimensions_endpoint:
                self.logger.warning(f"⚠ Rate Table '{rate_table_name}' (ID {rate_table_id}) has no Rate Dimensions defined. Proceeding with assignment anyway.")

            payload = {
                "RateTableId": rate_table_id,
                "RateTableName": rate_table_name,
                "IncentiveFormulaId": incentive_formula_id,
                "StartDate": start_date,
                "EndDate": end_date
            }
            self.logger.debug(f"Payload for Rate Table assignment: {payload}")
            endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}/child/planComponentRateTables"
            response, status_code = self.api_client.post(endpoint, payload)
            log_api_response(f"Assign Rate Table '{rate_table_name}' to Incentive Formula ID {incentive_formula_id}",
                            {"status_code": status_code, "response": response, "endpoint": endpoint, "payload": payload}, self.log_file)
            if status_code in [200, 201]:
                self.logger.info(f"✅ Successfully assigned Rate Table '{rate_table_name}' to Incentive Formula ID {incentive_formula_id}")
                rate_dimensional_inputs_endpoint = None
                for link in response.get("links", []):
                    if link.get("name") == "planComponentRateDimensionalInputs":
                        rate_dimensional_inputs_endpoint = link.get("href")
                        break
                if not rate_dimensional_inputs_endpoint:
                    self.logger.error(f"❌ No Rate Dimensional Inputs endpoint found in response for Rate Table '{rate_table_name}'. Response: {response}")
                    plan_component_rate_table_id = response.get("PlanComponentRateTableId")
                    if plan_component_rate_table_id:
                        rate_dimensional_inputs_endpoint = f"{endpoint}/{plan_component_rate_table_id}/child/planComponentRateDimensionalInputs"
                        self.logger.debug(f"Constructed RateDimensionalInputs endpoint: {rate_dimensional_inputs_endpoint}")
                    else:
                        return None
                self.logger.debug(f"Rate Dimensional Inputs endpoint: {rate_dimensional_inputs_endpoint}")
                return rate_dimensional_inputs_endpoint
            else:
                self.logger.error(f"❌ Failed to assign Rate Table: Status code {status_code}")
                self.logger.error(f"❌ Response details: {response}")
                return None
        except Exception as e:
            self.logger.exception(f"❌ Error assigning Rate Table: {e}")
            return None

    def assign_performance_measure_to_plan_component(self, plan_component_id: int, performance_measure_id: int, start_date: str, end_date: str, plan_components_uniq_id: str) -> Tuple[Any, int]:
        """Assign a Performance Measure to a Plan Component.

        Oracle POST payload for planComponentPerformanceMeasures (per API schema):
          - PerformanceMeasureId (int64, required)
          - PlanComponentId (int64, required — but auto-derived from URL path)
          - CalculationSequence (int32, default 1)
          - EarningBasis (string Y/N, default Y)
          - PerformanceMeasureWeight (int64, default 100)
        Note: StartDate/EndDate are NOT valid fields on this endpoint.
        """
        self.logger.info(f"🔧 Assigning Performance Measure ID {performance_measure_id} to Plan Component ID {plan_component_id}")
        endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentPerformanceMeasures"

        # Check if Performance Measure is already assigned to this Plan Component
        check_endpoint = f"{endpoint}?q=PerformanceMeasureId={performance_measure_id}"
        check_response, check_status = self.api_client.get(check_endpoint)
        if check_status == 200 and check_response.get("items"):
            self.logger.info(f"✅ Performance Measure ID {performance_measure_id} already assigned to Plan Component ID {plan_component_id}. Skipping.")
            return check_response["items"][0], 200

        payload = {
            "PerformanceMeasureId": performance_measure_id,
            "CalculationSequence": 1,
            "EarningBasis": "Y",
            "PerformanceMeasureWeight": 100,
        }
        response, status_code = self.api_client.post(endpoint, payload)
        log_api_response(f"Assign Performance Measure to Plan Component ID {plan_component_id}", {"status_code": status_code, "response": response}, self.log_file)
        # If POST fails with 400 (already assigned), treat as success
        if status_code == 400:
            self.logger.warning(f"⚠ POST returned 400 assigning Performance Measure. It may already be assigned.")
            check_response, check_status = self.api_client.get(check_endpoint)
            if check_status == 200 and check_response.get("items"):
                self.logger.info(f"✅ Confirmed Performance Measure already assigned. Continuing.")
                return check_response["items"][0], 200
        return response, status_code

    def configure_plan_components(self, force: bool = False) -> bool:
        self.logger.info("🔧 Starting Plan Component configuration process")
        try:
            plan_components = self.load_plan_components()
            if not plan_components:
                self.logger.warning("⚠ No valid Plan Components found in Excel.")
                return True

            self.logger.info(f"Loaded {len(plan_components)} valid Plan Components from Excel")
            success_count = 0
            error_count = 0

            for plan_component in plan_components:
                try:
                    self.logger.info(f"🔧 Creating Plan Component: {plan_component['Plan Component Name']}")
                    plan_component_id, incentive_formula_id, plan_components_uniq_id = self.get_plan_component_id(plan_component["Plan Component Name"])
                    if not plan_component_id:
                        self.logger.info(f"Creating new Plan Component: {plan_component['Plan Component Name']}")

                        # Map Excel field values to Oracle API field types
                        incentive_type = plan_component.get("Incentive Type", "COMMISSION")
                        calc_phase = plan_component.get("Calculation Phase", "1")
                        earning_type = plan_component.get("Earning Type", "-1000")
                        calc_incentive = plan_component.get("Calculate Incentive", "COMMISSION")

                        # CalculationPhase must be integer (1 or 2)
                        try:
                            calc_phase_int = int(str(calc_phase).strip().replace("Phase ", "").replace("phase ", ""))
                        except (ValueError, TypeError):
                            calc_phase_int = 1

                        # EarningType must be integer (-1000 = Monetary earnings)
                        try:
                            earning_type_int = int(str(earning_type).strip())
                        except (ValueError, TypeError):
                            # Map common display names to API codes
                            earning_type_map = {
                                "monetary earnings": -1000,
                                "monetary": -1000,
                            }
                            earning_type_int = earning_type_map.get(str(earning_type).strip().lower(), -1000)

                        plan_component_id, incentive_formula_id, plan_components_uniq_id = self.create_plan_component(
                            plan_component["Plan Component Name"],
                            plan_component["Start Date"],
                            plan_component["End Date"],
                            plan_component.get("Description", plan_component["Plan Component Name"]),
                            incentive_type=incentive_type,
                            calculation_phase=calc_phase_int,
                            earning_type=earning_type_int,
                            calculate_incentive=calc_incentive,
                        )
                        if not plan_component_id:
                            self.logger.error(f"❌ Failed to create Plan Component '{plan_component['Plan Component Name']}'. Skipping.")
                            error_count += 1
                            if not force:
                                return False
                            continue
                        self.logger.info(f"✅ Successfully created Plan Component with ID: {plan_component_id}")
                    else:
                        self.logger.info(f"✅ Plan Component '{plan_component['Plan Component Name']}' already exists with ID {plan_component_id}. Skipping creation.")

                    # Re-fetch to ensure we have the latest Incentive Formula ID
                    plan_component_id, incentive_formula_id, plan_components_uniq_id = self.get_plan_component_id(plan_component["Plan Component Name"])
                    if not incentive_formula_id:
                        self.logger.error(f"❌ No Incentive Formula ID found for Plan Component '{plan_component['Plan Component Name']}'. Skipping.")
                        error_count += 1
                        if not force:
                            return False
                        continue

                    # Assign Expression to Incentive Formula
                    expression_name = plan_component.get("Incentive Formula Expression")
                    if expression_name:
                        self.logger.info(f"🔧 Assigning Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}")
                        expression_id_org = self.get_expression_id(expression_name)
                        if expression_id_org:
                            expression_id, _ = expression_id_org

                            # Verify expression Status=VALID before assignment
                            # Oracle rejects assignment with 400 if expression is INVALID
                            expr_status = self._check_expression_status(expression_name)
                            if expr_status and expr_status != "VALID":
                                self.logger.warning(
                                    f"⚠ Expression '{expression_name}' has Status={expr_status}. "
                                    "Attempting assignment anyway (Oracle may reject with 400)."
                                )

                            response, status_code = self.assign_expression_to_incentive_formula(plan_component_id, incentive_formula_id, expression_id, plan_components_uniq_id)
                            log_api_response(f"Assign Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}",
                                            {"status_code": status_code, "response": response}, self.log_file)
                            if status_code in [200, 201]:
                                self.logger.info(f"✅ Successfully assigned Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}")
                            else:
                                self.logger.error(f"❌ Failed to assign Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}. Status: {status_code}")
                                if status_code == 400:
                                    self.logger.error(
                                        "💡 This usually means the expression has Status=INVALID. "
                                        "Ensure ExpressionDetails are correctly configured so "
                                        "Oracle can validate the expression formula."
                                    )
                                error_count += 1
                                if not force:
                                    return False
                                continue
                        else:
                            self.logger.error(f"❌ Expression '{expression_name}' not found. Skipping assignment.")
                            error_count += 1
                            if not force:
                                return False
                            continue

                    # Assign Performance Measure
                    performance_measure_name = plan_component.get("Performance Measure Name")
                    if performance_measure_name:
                        self.logger.debug(f"Found Performance Measure Name: {performance_measure_name}")
                        performance_measure_id = self.performance_measure_manager.get_performance_measure_id(performance_measure_name)
                        if performance_measure_id:
                            response, status_code = self.assign_performance_measure_to_plan_component(
                                plan_component_id,
                                performance_measure_id,
                                plan_component["Start Date"],
                                plan_component["End Date"],
                                plan_components_uniq_id
                            )
                            log_api_response(f"Assign Performance Measure '{performance_measure_name}' to Plan Component ID {plan_component_id}",
                                            {"status_code": status_code, "response": response}, self.log_file)
                            if status_code in [200, 201]:
                                self.logger.info(f"✅ Successfully assigned Performance Measure '{performance_measure_name}' to Plan Component ID {plan_component_id}")
                                success_count += 1
                            else:
                                self.logger.error(f"❌ Failed to assign Performance Measure '{performance_measure_name}' to Plan Component ID {plan_component_id}. Status: {status_code}")
                                error_count += 1
                                if not force:
                                    return False
                        else:
                            self.logger.error(f"❌ Performance Measure '{performance_measure_name}' not found. Skipping assignment.")
                            error_count += 1
                            if not force:
                                return False
                    else:
                        self.logger.warning(f"⚠ No Performance Measure Name found for Plan Component '{plan_component['Plan Component Name']}'. Skipping Performance Measure assignment.")

                    # Assign Rate Table to Incentive Formula
                    rate_table_name = plan_component.get("Rate Table Name")
                    if rate_table_name:
                        rate_dimensional_inputs_endpoint = self.assign_rate_table_to_incentive_formula(
                            plan_component_id,
                            incentive_formula_id,
                            rate_table_name,
                            plan_component["Start Date"],
                            plan_component["End Date"],
                            plan_components_uniq_id
                        )
                        if not rate_dimensional_inputs_endpoint:
                            self.logger.error(f"❌ Failed to assign Rate Table '{rate_table_name}' to Plan Component '{plan_component['Plan Component Name']}'. Skipping Rate Dimensional Input.")
                            error_count += 1
                            if not force:
                                return False
                            continue

                        # Assign Rate Dimensional Input (if Rate Table assignment succeeded)
                        if expression_name and rate_dimensional_inputs_endpoint:
                            self.logger.info(f"🔧 Assigning Rate Dimensional Input Expression '{expression_name}' to endpoint {rate_dimensional_inputs_endpoint}")
                            expression_id_org = self.get_expression_id(expression_name)
                            if expression_id_org:
                                expression_id, _ = expression_id_org

                                # Check if Rate Dimensional Input is already assigned
                                check_response, check_status = self.api_client.get(rate_dimensional_inputs_endpoint)
                                already_assigned = False
                                if check_status == 200 and check_response.get("items"):
                                    for rdi in check_response["items"]:
                                        if rdi.get("InputExpressionId") == expression_id:
                                            self.logger.info(f"✅ Rate Dimensional Input Expression '{expression_name}' already assigned. Skipping.")
                                            already_assigned = True
                                            break

                                if not already_assigned:
                                    # If existing items exist but with different expression,
                                    # PATCH the first one instead of POST (Oracle may reject
                                    # duplicate dimension assignments)
                                    if check_status == 200 and check_response.get("items"):
                                        existing_rdi = check_response["items"][0]
                                        rdi_id = existing_rdi.get("PlanComponentInputExpressionId")
                                        if rdi_id:
                                            self.logger.info(f"🔧 Updating existing Rate Dimensional Input {rdi_id} with new expression '{expression_name}'")
                                            patch_payload = {
                                                "InputExpressionId": expression_id,
                                                "InputExpressionName": expression_name
                                            }
                                            response, status_code = self.api_client.patch(
                                                f"{rate_dimensional_inputs_endpoint}/{rdi_id}", patch_payload
                                            )
                                            log_api_response(
                                                f"PATCH Rate Dimensional Input {rdi_id} with Expression '{expression_name}'",
                                                {"status_code": status_code, "response": response, "payload": patch_payload}, self.log_file
                                            )
                                            if status_code in [200, 201]:
                                                self.logger.info(f"✅ Successfully updated Rate Dimensional Input with Expression '{expression_name}'")
                                            elif status_code == 400:
                                                self.logger.warning(f"⚠ PATCH returned 400 for Rate Dimensional Input. Continuing.")
                                            else:
                                                self.logger.error(f"❌ Failed to update Rate Dimensional Input. Status: {status_code}")
                                                error_count += 1
                                                if not force:
                                                    return False
                                            continue

                                    payload = {
                                        "InputExpressionId": expression_id,
                                        "InputExpressionName": expression_name
                                    }
                                    response, status_code = self.api_client.post(rate_dimensional_inputs_endpoint, payload)
                                    log_api_response(f"Assign Rate Dimensional Input Expression '{expression_name}'",
                                                    {"status_code": status_code, "response": response, "endpoint": rate_dimensional_inputs_endpoint, "payload": payload}, self.log_file)
                                    if status_code in [200, 201]:
                                        self.logger.info(f"✅ Successfully assigned Rate Dimensional Input Expression '{expression_name}'")
                                    elif status_code == 400:
                                        # 400 often means "already assigned" — check and continue
                                        self.logger.warning(f"⚠ POST returned 400 for Rate Dimensional Input. It may already be assigned. Continuing.")
                                    else:
                                        self.logger.error(f"❌ Failed to assign Rate Dimensional Input Expression '{expression_name}'. Status: {status_code}, Response: {response}")
                                        error_count += 1
                                        if not force:
                                            return False
                                        continue
                            else:
                                self.logger.error(f"❌ Expression '{expression_name}' not found for Rate Dimensional Input.")
                                error_count += 1
                                if not force:
                                    return False
                                continue

                except Exception as e:
                    self.logger.exception(f"❌ Error configuring Plan Component '{plan_component['Plan Component Name']}': {e}")
                    error_count += 1
                    if not force:
                        return False

            self.logger.info(f"🔧 Plan Component configuration completed. {success_count} successful, {error_count} errors.")
            return error_count == 0
        except Exception as e:
            self.logger.exception(f"❌ Error in configure_plan_components: {e}")
            return False