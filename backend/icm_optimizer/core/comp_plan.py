"""
Compensation Plan Manager for Oracle ICM Plan Configuration Optimizer.
Handles creation and management of Compensation Plans and their Plan Components.
"""

import os
import time
import logging
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from ..utils.logging_utils import log_api_response

# app/core/comp_plan.py
import os
import logging
from typing import Optional
from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager

class CompensationPlanManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)

        # Define the compensation plan endpoint for Oracle ICM API
        self.compensation_plan_endpoint = "/fscmRestApi/resources/11.13.18.05/compensationPlans"  # Updated endpoint

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

    def create_compensation_plans_with_components(self, force: bool = False) -> bool:
        """Create compensation plans based on the Excel file."""
        if not self.excel_path:
            self.logger.error("No Excel file provided for compensation plans")
            return False
        self.logger.info(f"Creating compensation plans from {self.excel_path} for org_id: {self.org_id}")
        # Add your logic here to process the Excel file and create compensation plans
        try:
            compensation_plans = [
                {"name": "Compensation Plan 2025", "description": "Plan for 2025"}
            ]
            created_plans = 0
            for cp in compensation_plans:
                name = cp["name"]
                description = cp["description"]
                # Check if the compensation plan already exists
                query = f"{self.compensation_plan_endpoint}?q=Name='{name}';OrgId={self.org_id}"
                response, status_code = self.api_client.get(query)
                if status_code == 200 and response.get('items'):
                    self.logger.info(f"Skipping duplicate Compensation Plan: {name}")
                    continue
                # Create a new compensation plan
                payload = {
                    "Name": name,
                    "Description": description,
                    "OrgId": self.org_id
                }
                response, status_code = self.api_client.post(self.compensation_plan_endpoint, data=payload)
                if status_code == 201:
                    created_plans += 1
                    self.logger.info(f"Successfully created Compensation Plan: {name}")
                else:
                    self.logger.error(f"Failed to create Compensation Plan: {name}, Status Code: {status_code}, Response: {response}")
                    return False
            self.logger.info(f"Created {created_plans} Compensation Plans")
            return True
        except Exception as e:
            self.logger.error(f"Error in create_compensation_plans_with_components: {str(e)}")
            return False

    def load_compensation_plans(self) -> pd.DataFrame:
        """
        Load Compensation Plans from Excel file.

        Returns:
            DataFrame containing Compensation Plan data
        """
        try:
            self.logger.info(f"Loading Compensation Plans from {self.excel_path}")
            
            # Try both sheet name variations
            sheet_names = ["Compensation Plans", "Compensation Plan"]
            df = None
            
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                    self.logger.info(f"Successfully loaded '{sheet_name}' sheet")
                    break
                except ValueError:
                    self.logger.warning(f"Sheet '{sheet_name}' not found, trying alternative")
            
            if df is None:
                error_msg = f"No Compensation Plan sheet found in {self.excel_path}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)

            # Validate required columns
            required_columns = ["Name", "OrgId", "StartDate", "EndDate", "TargetIncentive"]
            
            # Check if any required columns are missing
            missing_columns = [
                col for col in required_columns if col not in df.columns]

            if missing_columns:
                if "OrgId" in missing_columns and "Org ID" in df.columns:
                    df["OrgId"] = df["Org ID"]
                    missing_columns.remove("OrgId")
                
                if "OrgId" in missing_columns:
                    self.logger.warning("OrgId column missing. Using default organization ID.")
                    df["OrgId"] = self.org_id
                    missing_columns.remove("OrgId")
                
                if missing_columns:
                    error_msg = f"Missing required columns in Compensation Plan sheet: {missing_columns}"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

            # Add default values for optional columns
            if "Description" not in df.columns:
                df["Description"] = df["Name"]
                
            if "DisplayName" not in df.columns:
                df["DisplayName"] = df["Name"]

            # Ensure data types are correct
            df["OrgId"] = df["OrgId"].astype(int)
            df["TargetIncentive"] = df["TargetIncentive"].astype(float)
            
            # Convert dates to string format if they're not already
            df["StartDate"] = pd.to_datetime(df["StartDate"]).dt.strftime('%Y-%m-%d')
            df["EndDate"] = pd.to_datetime(df["EndDate"]).dt.strftime('%Y-%m-%d')

            self.logger.info(f"Loaded {len(df)} Compensation Plans from Excel")
            return df
        except Exception as e:
            self.logger.error(f"Error loading Compensation Plans: {e}")
            raise

    def get_existing_plan_id(self, plan_name: str) -> Optional[int]:
        """
        Check if a Compensation Plan already exists by name.

        Args:
            plan_name: Name of the Compensation Plan

        Returns:
            Compensation Plan ID if found, None otherwise
        """
        self.logger.info(f"Checking if Compensation Plan exists: {plan_name}")

        try:
            # URL encode the plan name to handle special characters
            encoded_name = quote(plan_name)
            
            query_endpoint = f"{self.compensation_plan_endpoint}?q=Name='{encoded_name}'"
            response, status_code = self.api_client.get(query_endpoint)

            if status_code == 200 and "items" in response and response["items"]:
                plan_id = response["items"][0]["CompensationPlanId"]
                self.logger.info(f"Found existing Compensation Plan: {plan_name} with ID: {plan_id}")
                return plan_id
            else:
                self.logger.info(f"Compensation Plan '{plan_name}' does not exist")
                return None
        except Exception as e:
            self.logger.error(f"Error checking if Compensation Plan exists: {e}")
            return None

    def get_plan_component_id(self, component_name: str) -> Optional[int]:
        """
        Get Plan Component ID by name.

        Args:
            component_name: Name of the Plan Component

        Returns:
            Plan Component ID if found, None otherwise
        """
        self.logger.info(f"Retrieving Plan Component ID for: {component_name}")

        try:
            # URL encode the component name to handle special characters
            encoded_name = quote(component_name)
            
            query_endpoint = f"{self.compensation_plan_endpoint.replace('compensationPlans', 'planComponents')}?q=Name='{encoded_name}'"
            response, status_code = self.api_client.get(query_endpoint)

            if status_code == 200 and "items" in response and response["items"]:
                component_id = response["items"][0]["PlanComponentId"]
                self.logger.info(f"Found Plan Component ID: {component_id} for {component_name}")
                return component_id
            else:
                self.logger.info(f"Plan Component '{component_name}' not found.")
                return None
        except Exception as e:
            self.logger.error(f"Error retrieving Plan Component ID: {e}")
            return None

    def create_compensation_plan(
        self,
        name: str,
        org_id: int,
        start_date: str,
        end_date: str,
        target_incentive: float,
        description: str,
        display_name: str
    ) -> Optional[int]:
        """
        Create a new Compensation Plan.

        Args:
            name: Name of the Compensation Plan
            org_id: Organization ID
            start_date: Start date of the plan (YYYY-MM-DD)
            end_date: End date of the plan (YYYY-MM-DD)
            target_incentive: Target incentive amount
            description: Description of the plan
            display_name: Display name of the plan

        Returns:
            Compensation Plan ID if created, None if failed
        """
        self.logger.info(f"Creating Compensation Plan: {name}")

        # Check if plan already exists
        existing_plan_id = self.get_existing_plan_id(name)
        if existing_plan_id:
            self.logger.warning(f"Compensation Plan '{name}' already exists. Skipping creation.")
            return existing_plan_id

        # Prepare payload
        payload = {
            "Name": name.strip(),
            "OrgId": int(org_id),
            "StartDate": start_date,
            "EndDate": end_date,
            "TargetIncentive": float(target_incentive),
            "Description": description.strip(),
            "DisplayName": display_name.strip()
        }

        try:
            start_time = time.time()
            response, status_code = self.api_client.post(self.compensation_plan_endpoint, payload)

            # Log API response
            log_api_response(
                f"Create Compensation Plan: {name}",
                {"status_code": status_code, "text": str(response)},
                self.log_file  # Removed start_time parameter as per logging_utils.py
            )

            if status_code == 201 and "CompensationPlanId" in response:
                plan_id = response["CompensationPlanId"]
                self.logger.info(f"Successfully created Compensation Plan: {name} with ID: {plan_id}")
                return plan_id
            else:
                self.logger.error(f"Failed to create Compensation Plan: {name}")
                self.logger.error(f"Response details: {response}")
                return None
        except Exception as e:
            self.logger.exception(f"Error creating Compensation Plan {name}: {e}")
            return None

    def add_plan_component_to_compensation_plan(
        self,
        compensation_plan_id: int,
        plan_component_name: str,
        calculation_sequence: int = 1,
        target_incentive_percent: float = 100.0,
        start_date: str = None,
        end_date: str = None
    ) -> bool:
        """
        Add a Plan Component to a Compensation Plan.

        Args:
            compensation_plan_id: ID of the Compensation Plan
            plan_component_name: Name of the Plan Component to add
            calculation_sequence: Calculation sequence (default: 1)
            target_incentive_percent: Target incentive percent (default: 100.0)
            start_date: Start date (default: current year)
            end_date: End date (default: current year)

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Adding Plan Component '{plan_component_name}' to Compensation Plan ID: {compensation_plan_id}")

        # Get the Plan Component ID
        plan_component_id = self.get_plan_component_id(plan_component_name)
        if not plan_component_id:
            self.logger.error(f"Plan Component '{plan_component_name}' not found. Cannot add to Compensation Plan.")
            return False
            
        # Set default dates if not provided
        import datetime
        current_year = datetime.datetime.now().year
        if not start_date:
            start_date = f"{current_year}-01-01"
        if not end_date:
            end_date = f"{current_year}-12-31"

        # Prepare payload
        payload = {
            "PlanComponentId": plan_component_id,
            "CalculationSequence": int(calculation_sequence),
            "TargetIncentivePercent": float(target_incentive_percent),
            "StartDate": start_date,
            "EndDate": end_date,
            "CompensationPlanId": compensation_plan_id
        }

        try:
            # Endpoint for adding Plan Component to Compensation Plan
            endpoint = f"{self.compensation_plan_endpoint}/{compensation_plan_id}/child/CompensationPlanComponents"
            
            start_time = time.time()
            response, status_code = self.api_client.post(endpoint, payload)
            
            # Log API response
            log_api_response(
                f"Add Plan Component '{plan_component_name}' to Compensation Plan ID: {compensation_plan_id}",
                {"status_code": status_code, "text": str(response)},
                self.log_file  # Removed start_time parameter as per logging_utils.py
            )
            
            if status_code in [200, 201]:
                self.logger.info(f"Successfully added Plan Component '{plan_component_name}' to Compensation Plan ID: {compensation_plan_id}")
                return True
            else:
                self.logger.error(f"Failed to add Plan Component '{plan_component_name}' to Compensation Plan ID: {compensation_plan_id}")
                self.logger.error(f"Response details: {response}")
                return False
        except Exception as e:
            self.logger.exception(f"Error adding Plan Component to Compensation Plan: {e}")
            return False

    def create_compensation_plans_with_components(self, force: bool = False) -> bool:
        """
        Create Compensation Plans from Excel data and add Plan Components.

        Args:
            force: Whether to continue on error

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Starting Compensation Plan creation process with Plan Components")

        try:
            # Load Compensation Plans from Excel
            df = self.load_compensation_plans()
            
            # Process each Compensation Plan
            success_count = 0
            error_count = 0
            
            for _, row in df.iterrows():
                plan_name = row["Name"].strip()
                org_id = int(row["OrgId"])
                start_date = row["StartDate"]
                end_date = row["EndDate"]
                target_incentive = float(row["TargetIncentive"])
                description = row.get("Description", plan_name).strip()
                display_name = row.get("DisplayName", plan_name).strip()
                
                # Get or create the Compensation Plan
                existing_plan_id = self.get_existing_plan_id(plan_name)
                
                if existing_plan_id:
                    self.logger.info(f"Compensation Plan '{plan_name}' already exists. Using existing ID: {existing_plan_id}")
                    plan_id = existing_plan_id
                else:
                    # Create the Compensation Plan
                    plan_id = self.create_compensation_plan(
                        plan_name,
                        org_id,
                        start_date,
                        end_date,
                        target_incentive,
                        description,
                        display_name
                    )
                    
                    if not plan_id:
                        error_count += 1
                        if not force:
                            self.logger.error(f"Stopping due to error with plan: {plan_name}")
                            return False
                        continue
                
                # Check if there's a Plan Component to add
                if "Plan Component Name" in row and pd.notna(row["Plan Component Name"]):
                    plan_component_name = row["Plan Component Name"].strip()
                    
                    # Get additional component parameters if available
                    calculation_sequence = int(row.get("CalculationSequence", 1)) if pd.notna(row.get("CalculationSequence", 1)) else 1
                    target_incentive_percent = float(row.get("TargetIncentivePercent", 100.0)) if pd.notna(row.get("TargetIncentivePercent", 100.0)) else 100.0
                    
                    # Get component dates or use plan dates as default
                    component_start_date = row.get("ComponentStartDate", start_date) if pd.notna(row.get("ComponentStartDate", start_date)) else start_date
                    component_end_date = row.get("ComponentEndDate", end_date) if pd.notna(row.get("ComponentEndDate", end_date)) else end_date
                    
                    # Add the Plan Component to the Compensation Plan
                    component_added = self.add_plan_component_to_compensation_plan(
                        plan_id,
                        plan_component_name,
                        calculation_sequence,
                        target_incentive_percent,
                        component_start_date,
                        component_end_date
                    )
                    
                    if not component_added:
                        self.logger.warning(f"Failed to add Plan Component '{plan_component_name}' to Plan '{plan_name}'")
                        if not force:
                            return False
                
                success_count += 1
            
            self.logger.info(f"Compensation Plan creation completed with components. {success_count} successful, {error_count} errors.")
            return True
            
        except Exception as e:
            self.logger.exception(f"Error in create_compensation_plans_with_components: {e}")
            return False