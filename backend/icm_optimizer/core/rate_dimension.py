"""
Rate Dimension Manager for Oracle ICM Plan Configuration Optimizer.
Handles creation and management of Rate Dimensions and their tiers.
"""

import os
import logging
import pandas as pd
from typing import Optional, List, Dict, Any
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from ..utils.logging_utils import log_api_response

class RateDimensionManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file  # Path to objects_created.log
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)

        # Define the rate dimension endpoint for Oracle ICM API
        self.rate_dimension_endpoint = "/rateDimensions"  # Use relative path to avoid duplication

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

    def load_rate_dimensions(self) -> pd.DataFrame:
        """
        Load Rate Dimensions from Excel file.

        Returns:
            DataFrame containing Rate Dimension data
        """
        try:
            self.logger.info(f"Loading Rate Dimensions from {self.excel_path}")
            df = pd.read_excel(self.excel_path, sheet_name="Rate Dimension")
            if df.empty:
                self.logger.warning("Rate Dimension sheet is empty")
                return pd.DataFrame()
            return df.rename(columns={"Rate Dimension Name": "Name"})
        except Exception as e:
            self.logger.error(f"Error loading Rate Dimensions: {e}")
            raise

    def load_rate_dimension_tiers(self, dimension_name: str) -> List[Dict[str, Any]]:
        """
        Load Rate Dimension Tiers from the 'Rate Dimension' sheet for a specific dimension.

        Args:
            dimension_name: Name of the Rate Dimension

        Returns:
            List of tier configurations
        """
        try:
            self.logger.info(f"Loading Rate Dimension Tiers for {dimension_name} from {self.excel_path}")
            df = pd.read_excel(self.excel_path, sheet_name="Rate Dimension")
            tiers_df = df[df["Rate Dimension Name"] == dimension_name][["Tier Sequence", "Minimum Amount", "Maximum Amount"]].dropna()
            if tiers_df.empty:
                self.logger.warning(f"No tiers found for Rate Dimension: {dimension_name}")
                return []
            tiers = [{"MinimumAmount": float(row["Minimum Amount"]), "MaximumAmount": float(row["Maximum Amount"])} for _, row in tiers_df.iterrows()]
            self.logger.info(f"Loaded tiers for {dimension_name}: {tiers}")
            return tiers
        except Exception as e:
            self.logger.error(f"Error loading Rate Dimension Tiers for {dimension_name}: {e}")
            return []

    def get_rate_dimension_id(self, name: str) -> Optional[int]:
        """
        Retrieve Rate Dimension ID by name and OrgId.

        Args:
            name: Name of the Rate Dimension

        Returns:
            Rate Dimension ID if found, None otherwise
        """
        self.logger.info(f"Retrieving Rate Dimension ID for: {name} with OrgId: {self.org_id}")
        try:
            encoded_name = quote(name)
            query_endpoint = f"{self.rate_dimension_endpoint}?q=Name='{encoded_name}';OrgId={self.org_id}"
            response, status_code = self.api_client.get(query_endpoint)
            log_api_response(f"Get Rate Dimension by Name: {name}, OrgId: {self.org_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and response.get("items"):
                self.logger.info(f"Found Rate Dimension ID: {response['items'][0]['RateDimensionId']} with NumberTier: {response['items'][0].get('NumberTier', 0)}")
                return int(response["items"][0]["RateDimensionId"])
            self.logger.info(f"Rate Dimension '{name}' not found for OrgId: {self.org_id}.")
            # Create new dimension
            payload = {
                "Name": name,
                "RateDimensionType": "AMOUNT",
                "OrgId": self.org_id
            }
            response, status_code = self.api_client.post(self.rate_dimension_endpoint, payload)
            log_api_response(f"Create Rate Dimension: {name}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201:
                dimension_id = int(response["RateDimensionId"])
                self.logger.info(f"Successfully created Rate Dimension: {name} with ID: {dimension_id}")
                return dimension_id
            self.logger.error(f"Failed to create Rate Dimension {name}: {response.get('message', 'No message')}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving/creating Rate Dimension ID: {e}")
            return None

    def create_rate_dimension(self, name: str, description: str, rate_dimension_type: str = "AMOUNT") -> Optional[int]:
        """
        Create a new Rate Dimension.

        Args:
            name: Name of the Rate Dimension
            description: Description of the Rate Dimension
            rate_dimension_type: Type of the rate dimension (e.g., AMOUNT, PERCENT)

        Returns:
            Rate Dimension ID if created, None otherwise
        """
        self.logger.info(f"Creating new Rate Dimension: {name} with type: {rate_dimension_type} and OrgId: {self.org_id}")
        payload = {
            "Name": name,
            "Description": description,
            "RateDimensionType": rate_dimension_type.upper(),
            "OrgId": self.org_id
        }
        try:
            response, status_code = self.api_client.post(self.rate_dimension_endpoint, payload)
            log_api_response(f"Create Rate Dimension: {name}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201:
                self.logger.info(f"Successfully created Rate Dimension: {name} with ID: {response['RateDimensionId']}")
                return int(response["RateDimensionId"])
            self.logger.error(f"Failed to create Rate Dimension: {response.get('message', 'No message')}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating Rate Dimension: {e}")
            return None

    def update_rate_dimension_tiers(self, rate_dimension_id: int, tiers: List[Dict[str, Any]]) -> bool:
        """
        Update Rate Dimension with tiers by creating new ones.

        Args:
            rate_dimension_id: ID of the Rate Dimension
            tiers: List of tier configurations with ranges

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Updating tiers for Rate Dimension ID: {rate_dimension_id}")
        try:
            endpoint = f"{self.rate_dimension_endpoint}/{rate_dimension_id}/child/RateDimensionTiers"
            response, status_code = self.api_client.get(endpoint)
            log_api_response(f"Get Rate Dimension Tiers for Dimension ID: {rate_dimension_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            existing_tiers = {}
            if status_code == 200 and "items" in response:
                self.logger.info(f"Found {len(response['items'])} existing tiers for Rate Dimension ID: {rate_dimension_id}")
                for tier in response["items"]:
                    existing_tiers[(tier["MinimumAmount"], tier["MaximumAmount"])] = {
                        "RateDimTierId": tier["RateDimTierId"],
                        "TierSequence": tier["TierSequence"]
                    }
            else:
                self.logger.warning(f"No tiers found for Rate Dimension ID: {rate_dimension_id}. Status Code: {status_code}. Forcing tier creation.")
                existing_tiers = {}

            success = True
            for tier in tiers:
                tier_key = (tier.get("MinimumAmount", 0), tier.get("MaximumAmount", 1000000))
                if tier_key not in existing_tiers:
                    self.logger.info(f"Creating new Tier for Range {tier_key} in Rate Dimension ID: {rate_dimension_id}")
                    tier_payload = {
                        "RateDimensionId": rate_dimension_id,
                        "MinimumAmount": tier.get("MinimumAmount", 0),
                        "MaximumAmount": tier.get("MaximumAmount", 1000000)
                    }
                    response, status_code = self.api_client.post(endpoint, tier_payload)
                    log_api_response(f"Create Rate Dimension Tier: Dimension {rate_dimension_id}, Range {tier_key}",
                                    {"status_code": status_code, "response": response}, self.log_file)
                    if status_code != 201:
                        self.logger.error(f"Failed to create Tier for Range {tier_key} for Rate Dimension {rate_dimension_id}: {response.get('message', 'No message')}")
                        success = False
                else:
                    self.logger.info(f"Tier for Range {tier_key} in Rate Dimension {rate_dimension_id} already exists")
            return success
        except Exception as e:
            self.logger.error(f"Error updating Rate Dimension Tiers: {e}")
            return False

    def create_rate_dimensions(self, force: bool = False) -> bool:
        """
        Create or update Rate Dimensions and their tiers from Excel.

        Args:
            force: Whether to force creation even if errors occur

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Starting Rate Dimension creation process")
        try:
            df = self.load_rate_dimensions()
            self.logger.info(f"Loaded {len(df)} Rate Dimensions from Excel")

            created_dimensions = 0
            processed_names = set()  # To avoid duplicate processing

            for _, row in df.iterrows():
                name = row["Name"]
                if name in processed_names:
                    self.logger.info(f"Skipping duplicate Rate Dimension: {name}")
                    continue
                processed_names.add(name)

                description = row.get("Description", name)
                rate_dimension_type = row.get("RateDimensionType", "AMOUNT").upper()
                self.logger.debug(f"Processing Rate Dimension: {name} with type: {rate_dimension_type} and OrgId: {self.org_id}")
                rate_dimension_id = self.get_rate_dimension_id(name)

                if rate_dimension_id is None:
                    rate_dimension_id = self.create_rate_dimension(name, description, rate_dimension_type)
                    if rate_dimension_id is None:
                        if not force:
                            return False
                        continue
                else:
                    self.logger.info(f"Rate dimension '{name}' already exists with ID {rate_dimension_id} for OrgId: {self.org_id}")

                # Load and update tiers from the same 'Rate Dimension' sheet
                tiers = self.load_rate_dimension_tiers(name)
                if not tiers:
                    self.logger.warning(f"No tiers defined for Rate Dimension: {name}. Skipping tier update.")
                elif not self.update_rate_dimension_tiers(rate_dimension_id, tiers):
                    if not force:
                        return False
                    continue

                created_dimensions += 1

            self.logger.info("Rate Dimension processing completed!")
            self.logger.info(f"Created Dimensions: {created_dimensions}")
            return True if created_dimensions > 0 else False
        except Exception as e:
            self.logger.error(f"Error in create_rate_dimensions: {e}")
            return False