import os
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from ..utils.logging_utils import log_api_response

class PerformanceMeasureManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)

        # Define the performance measure endpoint for Oracle ICM API
        self.performance_measure_endpoint = "/fscmRestApi/resources/11.13.18.05/incentiveCompensationPerformanceMeasures"

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

    def load_performance_measures(self) -> List[Dict[str, Any]]:
        try:
            df = pd.read_excel(self.excel_path, sheet_name='Performance Measures', dtype=str)
            df = df.where(pd.notnull(df), None)
            required_columns = ['Name', 'Credit Category Name', 'Start Date', 'End Date']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"❌ Missing required columns in 'Performance Measures' sheet: {missing_columns}")
                return []
            performance_measures = df.to_dict('records')
            return performance_measures
        except Exception as e:
            self.logger.exception(f"❌ Error loading Performance Measures from Excel: {e}")
            return []

    def get_performance_measure_id(self, name: str) -> Optional[int]:
        self.logger.info(f"🔍 Retrieving Performance Measure ID for: {name}")
        endpoint = f"{self.performance_measure_endpoint}?q=Name='{quote(name)}';OrgId={self.org_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Performance Measure by Name: {name}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            performance_measure = response["items"][0]
            performance_measure_id = performance_measure.get("PerformanceMeasureId")
            self.logger.info(f"✅ Found Performance Measure '{name}' with ID: {performance_measure_id}")
            return performance_measure_id
        self.logger.warning(f"⚠ Performance Measure '{name}' not found.")
        return None

    def get_credit_category_id(self, credit_category_name: str) -> Optional[int]:
        """Look up Credit Category by name and OrgId.

        If exact name+OrgId match fails, falls back to:
        1. Name-only search (OrgId may differ for shared categories)
        2. Partial name match (e.g. "Sales Credit" → "Sales Credit Category")
        """
        self.logger.info(f"🔍 Retrieving Credit Category ID for: {credit_category_name} with OrgId: {self.org_id}")
        credit_category_endpoint = "/fscmRestApi/resources/11.13.18.05/creditCategories"

        # Primary: exact name + OrgId
        endpoint = f"{credit_category_endpoint}?q=Name='{quote(credit_category_name)}';OrgId={self.org_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Credit Category by Name: {credit_category_name}, OrgId: {self.org_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            credit_category = response["items"][0]
            credit_category_id = credit_category.get("CreditCategoryId")
            self.logger.info(f"✅ Found Credit Category ID: {credit_category_id}")
            return credit_category_id

        # Fallback 1: name only (shared categories may not be scoped to OrgId)
        self.logger.info(f"⚠ Credit Category '{credit_category_name}' not found with OrgId {self.org_id}. Trying name-only lookup.")
        endpoint = f"{credit_category_endpoint}?q=Name='{quote(credit_category_name)}'"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Credit Category by Name only: {credit_category_name}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            credit_category = response["items"][0]
            credit_category_id = credit_category.get("CreditCategoryId")
            self.logger.info(f"✅ Found Credit Category ID: {credit_category_id} (name-only match, OrgId: {credit_category.get('OrgId')})")
            return credit_category_id

        # Fallback 2: list all credit categories for this org and log available names
        self.logger.info(f"⚠ Credit Category '{credit_category_name}' not found by name. Listing available categories for OrgId {self.org_id}.")
        endpoint = f"{credit_category_endpoint}?q=OrgId={self.org_id}&limit=50"
        response, status_code = self.api_client.get(endpoint)
        if status_code == 200 and response.get("items"):
            available_names = [item.get("Name", "?") for item in response["items"]]
            self.logger.info(f"📋 Available Credit Categories for OrgId {self.org_id}: {available_names}")
            # Try case-insensitive partial match
            for item in response["items"]:
                if credit_category_name.lower() in item.get("Name", "").lower():
                    credit_category_id = item.get("CreditCategoryId")
                    self.logger.info(f"✅ Found partial match: '{item['Name']}' (ID: {credit_category_id})")
                    return credit_category_id

        # Fallback 3: create the credit category if it doesn't exist
        self.logger.info(f"🔧 Credit Category '{credit_category_name}' not found anywhere. Attempting to create it.")
        created_id = self.create_credit_category(credit_category_name)
        if created_id:
            return created_id

        self.logger.error(f"❌ Credit Category '{credit_category_name}' could not be found or created in Oracle instance.")
        return None

    def create_credit_category(self, name: str) -> Optional[int]:
        """Create a new Credit Category in Oracle ICM.

        Posts to /creditCategories with the given name and current OrgId.
        If creation fails with 400 (already exists), attempts to look it up.
        Returns the CreditCategoryId on success, None on failure.
        """
        self.logger.info(f"🔧 Creating new Credit Category: {name}")
        credit_category_endpoint = "/fscmRestApi/resources/11.13.18.05/creditCategories"

        payload = {
            "Name": name,
            "OrgId": self.org_id,
            "Description": f"Credit Category for {name}"
        }
        response, status_code = self.api_client.post(credit_category_endpoint, payload)
        log_api_response(f"Create Credit Category: {name}", {"status_code": status_code, "response": response}, self.log_file)

        if status_code in [200, 201]:
            credit_category_id = response.get("CreditCategoryId")
            self.logger.info(f"✅ Successfully created Credit Category '{name}' with ID: {credit_category_id}")
            return credit_category_id

        # If creation failed (e.g., 400 "already exists"), try to fetch the existing one
        if status_code == 400:
            self.logger.warning(f"⚠ POST returned 400 for Credit Category '{name}'. It may already exist — attempting lookup.")
            # Try exact name search (without OrgId constraint in case it's shared)
            endpoint = f"{credit_category_endpoint}?q=Name='{quote(name)}'"
            resp, sc = self.api_client.get(endpoint)
            if sc == 200 and resp.get("items"):
                credit_category_id = resp["items"][0].get("CreditCategoryId")
                self.logger.info(f"✅ Found existing Credit Category '{name}' with ID: {credit_category_id}")
                return credit_category_id

        self.logger.error(f"❌ Failed to create Credit Category '{name}'. Status: {status_code}, Response: {response}")
        return None

    def create_performance_measure(self, name: str, start_date: str, end_date: str) -> Optional[int]:
        self.logger.info(f"🔧 Creating new Performance Measure: {name}")
        # Note: ValidForCalculation is read-only — Oracle sets it automatically.
        payload = {
            "Name": name,
            "OrgId": self.org_id,
            "StartDate": start_date,
            "EndDate": end_date,
            "UnitOfMeasure": "AMOUNT",
            "IncludeInParticipantReportsFlag": True,
            "ProcessTransactions": "INDIVIDUAL",
            "PerformanceInterval": "-1000",
            "DisplayName": name
        }
        response, status_code = self.api_client.post(self.performance_measure_endpoint, payload)
        log_api_response(f"Create Performance Measure: {name}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code in [200, 201]:
            performance_measure_id = response.get("PerformanceMeasureId")
            self.logger.info(f"✅ Successfully created Performance Measure '{name}' with ID: {performance_measure_id}")
            return performance_measure_id
        # If creation failed (e.g., 400 "already exists"), try to fetch the existing one
        if status_code == 400:
            self.logger.warning(f"⚠ POST returned 400 for Performance Measure '{name}'. Checking if it already exists.")
            existing_id = self.get_performance_measure_id(name)
            if existing_id:
                self.logger.info(f"✅ Found existing Performance Measure '{name}' with ID: {existing_id}")
                return existing_id
        self.logger.error(f"❌ Failed to create Performance Measure '{name}'. Status: {status_code}, Response: {response}")
        return None

    def assign_credit_category(self, performance_measure_id: int, credit_category_name: str) -> bool:
        self.logger.info(f"🔧 Assigning Credit Category '{credit_category_name}' to Performance Measure ID {performance_measure_id}")
        credit_category_id = self.get_credit_category_id(credit_category_name)
        if not credit_category_id:
            self.logger.error(f"❌ Cannot assign Credit Category '{credit_category_name}' due to missing ID.")
            return False

        self.logger.info(f"🔍 Checking if Credit Category ID {credit_category_id} is assigned to Performance Measure ID {performance_measure_id}")
        endpoint = f"{self.performance_measure_endpoint}/{performance_measure_id}/child/performanceMeasureCreditCategories?q=CreditCategoryId={credit_category_id}"
        response, status_code = self.api_client.get(endpoint)
        log_api_response(f"Get Credit Categories for Performance Measure ID: {performance_measure_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200 and response.get("items"):
            self.logger.info(f"✅ Credit Category '{credit_category_name}' already assigned to Performance Measure ID {performance_measure_id}. Skipping.")
            return True

        payload = {
            "CreditCategoryId": credit_category_id,
            "CreditCategoryName": credit_category_name
        }
        endpoint = f"{self.performance_measure_endpoint}/{performance_measure_id}/child/performanceMeasureCreditCategories"
        response, status_code = self.api_client.post(endpoint, payload)
        log_api_response(f"Assign Credit Category '{credit_category_name}' to Performance Measure ID {performance_measure_id}", {"status_code": status_code, "response": response}, self.log_file)
        if status_code in [200, 201]:
            self.logger.info(f"✅ Successfully assigned Credit Category '{credit_category_name}' to Performance Measure ID {performance_measure_id}")
            return True
        self.logger.error(f"❌ Failed to assign Credit Category '{credit_category_name}' to Performance Measure ID {performance_measure_id}. Status: {status_code}")
        return False

    def create_performance_measures(self, force: bool = False) -> bool:
        self.logger.info("🔧 Starting Performance Measure creation process")
        performance_measures = self.load_performance_measures()
        if not performance_measures:
            self.logger.warning("⚠ No Performance Measures found in Excel.")
            return True

        self.logger.info(f"Loaded {len(performance_measures)} Performance Measures from Excel")
        success_count = 0
        error_count = 0

        for pm in performance_measures:
            try:
                name = pm["Name"]
                self.logger.info(f"🔧 Processing Performance Measure: {name}")
                performance_measure_id = self.get_performance_measure_id(name)
                if performance_measure_id:
                    self.logger.info(f"✅ Performance Measure '{name}' already exists with ID: {performance_measure_id}. Skipping creation.")
                else:
                    self.logger.info(f"Creating new Performance Measure: {name}")
                    performance_measure_id = self.create_performance_measure(
                        name,
                        pm["Start Date"],
                        pm["End Date"]
                    )
                    if not performance_measure_id:
                        self.logger.error(f"❌ Failed to create Performance Measure '{name}'.")
                        error_count += 1
                        if not force:
                            return False
                        continue
                    self.logger.info(f"✅ Created Performance Measure '{name}' with ID: {performance_measure_id}")

                credit_category_name = pm.get("Credit Category Name")
                if credit_category_name:
                    if not self.assign_credit_category(performance_measure_id, credit_category_name):
                        self.logger.error(f"❌ Failed to assign Credit Category '{credit_category_name}' to Performance Measure '{name}'.")
                        error_count += 1
                        if not force:
                            return False
                        continue
                success_count += 1
            except Exception as e:
                self.logger.exception(f"❌ Error processing Performance Measure '{pm.get('Name', 'Unknown')}': {e}")
                error_count += 1
                if not force:
                    return False

        self.logger.info(f"✅ Performance Measure processing completed!")
        self.logger.info(f"📊 Created Performance Measures: {success_count}")
        return error_count == 0