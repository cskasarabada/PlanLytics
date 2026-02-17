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

# app/core/plan_component.py
import os
import logging
from typing import Optional
from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from .perf_measure import PerformanceMeasureManager

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

    def configure_plan_components(self, force: bool = False) -> bool:
        """Configure plan components based on the Excel file."""
        if not self.excel_path:
            self.logger.error("No Excel file provided for plan components")
            return False
        self.logger.info(f"Configuring plan components from {self.excel_path} for org_id: {self.org_id}")
        # Add your logic here to process the Excel file and configure plan components
        try:
            plan_components = [
                {"name": "Solutions Director Plan 2025", "performance_measure": "Arg Credit Amount 2025"},
            ]
            created_components = 0
            for pc in plan_components:
                name = pc["name"]
                performance_measure = pc["performance_measure"]
                # Check if the plan component already exists
                query = f"{self.plan_component_endpoint}?q=Name='{name}';OrgId={self.org_id}"
                response, status_code = self.api_client.get(query)
                if status_code == 200 and response.get('items'):
                    self.logger.info(f"Skipping duplicate Plan Component: {name}")
                    continue
                # Create a new plan component
                payload = {
                    "Name": name,
                    "PerformanceMeasure": performance_measure,
                    "OrgId": self.org_id
                }
                response, status_code = self.api_client.post(self.plan_component_endpoint, data=payload)
                if status_code == 201:
                    created_components += 1
                    self.logger.info(f"Successfully created Plan Component: {name}")
                    self.logger.debug(f"Found Performance Measure Name: {performance_measure}")
                    self.logger.info(f"✅ Successfully assigned Performance Measure '{performance_measure}' to Plan Component ID {response.get('PlanComponentId', '300000300009597')}")
                else:
                    self.logger.error(f"Failed to create Plan Component: {name}, Status Code: {status_code}, Response: {response}")
                    return False
            self.logger.info(f"Created {created_components} Plan Components")
            return True
        except Exception as e:
            self.logger.error(f"Error in configure_plan_components: {str(e)}")
            return False

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

    def create_plan_component(self, name: str, start_date: str, end_date: str, description: str = None) -> Optional[Tuple[int, int, str]]:
        endpoint = f"{self.plan_component_endpoint}"
        payload = {
            "Name": name,
            "OrgId": self.org_id,
            "StartDate": start_date,
            "EndDate": end_date,
            "Description": description if description else name,
            "IncentiveType": "COMMISSION",
            "CalculateIncentive": "Per event",
            "EarningType": "Monetary earnings",
            "CalculationPhase": "Phase 1",
            "ValidForCalculation": "No",
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
        self.logger.error(f"❌ Failed to create Plan Component '{name}'. Status: {status_code}, Response: {response}")
        return None, None, None

    def get_expression_id(self, expression_name: str) -> Optional[Tuple[int, int]]:
        self.logger.info(f"🔍 Retrieving Expression ID for: {expression_name}")
        try:
            endpoint = f"{self.plan_component_endpoint.replace('planComponents', 'incentiveCompensationExpressions')}?q=Name='{quote(expression_name)}'"
            response, status_code = self.api_client.get(endpoint)
            if status_code != 200 or not response.get("items"):
                self.logger.error(f"❌ Failed to retrieve Expressions to find ExpressionVO. Status: {status_code}")
                return None

            expression = response["items"][0]
            expression_vo_href = None
            for link in expression.get("links", []):
                if link.get("name") == "ExpressionVO":
                    expression_vo_href = link.get("href")
                    break

            if not expression_vo_href:
                self.logger.error(f"❌ ExpressionVO link not found in Expression response.")
                return None

            self.logger.debug(f"Using ExpressionVO endpoint: {expression_vo_href}")
            endpoint = f"{expression_vo_href}?q=Name='{quote(expression_name)}'"
            response, status_code = self.api_client.get(endpoint)
            if status_code == 200 and response.get("items"):
                expression = response["items"][0]
                expression_id = expression.get("ExpressionId")
                org_id = expression.get("OrgId")
                self.logger.info(f"✅ Found Expression ID: {expression_id}, OrgId: {org_id} via ExpressionVO")
                return expression_id, org_id
            else:
                self.logger.error(f"❌ Expression '{expression_name}' not found via ExpressionVO. Status: {status_code}")
                return None
        except Exception as e:
            self.logger.exception(f"❌ Error retrieving Expression ID via ExpressionVO: {e}")
            return None

    def assign_expression_to_incentive_formula(self, plan_component_id: int, incentive_formula_id: int, expression_id: int, plan_components_uniq_id: str) -> Tuple[Any, int]:
        endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentIncentiveFormulas/{incentive_formula_id}"
        payload = {
            "ExpressionId": expression_id
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
        self.logger.info(f"🔧 Assigning Performance Measure ID {performance_measure_id} to Plan Component ID {plan_component_id}")
        endpoint = f"{self.plan_component_endpoint}/{plan_components_uniq_id}/child/planComponentPerformanceMeasures"
        payload = {
            "PerformanceMeasureId": performance_measure_id,
            "StartDate": start_date,
            "EndDate": end_date
        }
        response, status_code = self.api_client.post(endpoint, payload)
        log_api_response(f"Assign Performance Measure to Plan Component ID {plan_component_id}", {"status_code": status_code, "response": response}, self.log_file)
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
                        plan_component_id, incentive_formula_id, plan_components_uniq_id = self.create_plan_component(
                            plan_component["Plan Component Name"],
                            plan_component["Start Date"],
                            plan_component["End Date"],
                            plan_component["Description"]
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
                            response, status_code = self.assign_expression_to_incentive_formula(plan_component_id, incentive_formula_id, expression_id, plan_components_uniq_id)
                            log_api_response(f"Assign Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}",
                                            {"status_code": status_code, "response": response}, self.log_file)
                            if status_code in [200, 201]:
                                self.logger.info(f"✅ Successfully assigned Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}")
                            else:
                                self.logger.error(f"❌ Failed to assign Expression '{expression_name}' to Incentive Formula ID {incentive_formula_id}. Status: {status_code}")
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
                                payload = {
                                    "InputExpressionId": expression_id,
                                    "InputExpressionName": expression_name
                                }
                                response, status_code = self.api_client.post(rate_dimensional_inputs_endpoint, payload)
                                log_api_response(f"Assign Rate Dimensional Input Expression '{expression_name}'",
                                                {"status_code": status_code, "response": response, "endpoint": rate_dimensional_inputs_endpoint, "payload": payload}, self.log_file)
                                if status_code in [200, 201]:
                                    self.logger.info(f"✅ Successfully assigned Rate Dimensional Input Expression '{expression_name}'")
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