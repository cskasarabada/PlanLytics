"""
Rate Table Manager for Oracle ICM Plan Configuration Optimizer.
Handles creation and configuration of Rate Tables.
"""

import os
import logging
import pandas as pd
from typing import Tuple, Dict, Any, Optional, List
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from ..utils.logging_utils import log_api_response

class RateTableManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file  # Use log_file instead of objects_file
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)
        self.rate_table_endpoint = "/rateTables"

        organization_section = self.config_manager.get('organization') or {}
        self.org_id = organization_section.get('org_id', None)
        if not self.org_id:
            self.logger.error("No org_id found in configuration")
            raise ValueError("No org_id found in configuration")

        if self.excel_path and not self._validate_excel_file():
            raise FileNotFoundError(f"Excel file not found: {self.excel_path}")

    def _validate_excel_file(self) -> bool:
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

    def get_rate_table_id(self, name: str) -> Optional[int]:
        self.logger.info(f"Retrieving Rate Table ID for: {name} with OrgId: {self.org_id}")
        try:
            query = f"?q=Name='{quote(name)}';OrgId={self.org_id}"
            response, status_code = self.api_client.get(f"{self.rate_table_endpoint}{query}")
            log_api_response(f"Get Rate Table by Name: {name}, OrgId: {self.org_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and response.get("items"):
                return int(response["items"][0]["RateTableId"])
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving Rate Table ID: {e}")
            return None

    def create_rate_table(self, name: str) -> Optional[int]:
        self.logger.info(f"Creating new Rate Table: {name} with OrgId: {self.org_id}")
        payload = {
            "Name": name,
            "OrgId": self.org_id,
            "RateTableType": "AMOUNT",
            "DisplayName": name,
            "Description": name
        }
        try:
            response, status_code = self.api_client.post(self.rate_table_endpoint, payload)
            log_api_response(f"Create Rate Table: {name}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201:
                return int(response["RateTableId"])
            # If creation failed with 400 (likely already exists), try to fetch existing
            if status_code == 400:
                self.logger.warning(f"POST returned 400 for Rate Table '{name}'. Re-checking if it exists.")
                existing_id = self.get_rate_table_id(name)
                if existing_id:
                    self.logger.info(f"Found existing Rate Table '{name}' with ID: {existing_id}")
                    return existing_id
            self.logger.error(f"Failed to create Rate Table: {response.get('message', 'No message') if isinstance(response, dict) else response}")
            return None
        except Exception as e:
            self.logger.error(f"Error creating Rate Table: {e}")
            return None

    def load_rate_tables(self) -> pd.DataFrame:
        """
        Load Rate Tables from Excel file.

        Returns:
            DataFrame containing Rate Table data
        """
        try:
            self.logger.info(f"Loading Rate Tables from {self.excel_path}")
            df = pd.read_excel(self.excel_path, sheet_name="Rate Table")
            if df.empty:
                self.logger.warning("No data found in Rate Table sheet")
            return df
        except Exception as e:
            self.logger.error(f"Error loading Rate Tables: {e}")
            raise

    def load_rate_table_rates(self) -> pd.DataFrame:
        """
        Load Rate Table Rates from Excel file.

        Returns:
            DataFrame containing Rate Table Rates data
        """
        try:
            self.logger.info(f"Loading Rate Table Rates from {self.excel_path}")
            df = pd.read_excel(self.excel_path, sheet_name="Rate Table Rates")
            if "Rate Value" in df.columns:
                self.logger.info(f"Detected 'Rate Value' column as RateValue")
                df["RateValue"] = pd.to_numeric(df["Rate Value"], errors="coerce")
            else:
                df["RateValue"] = pd.to_numeric(df.iloc[:, df.columns.get_loc("Rate Value") if "Rate Value" in df.columns else -1], errors="coerce")
            if df.empty:
                self.logger.warning("No data found in Rate Table Rates sheet")
            return df
        except Exception as e:
            self.logger.error(f"Error loading Rate Table Rates: {e}")
            raise

    def get_rate_dimension_id(self, dimension_name: str) -> Optional[int]:
        """
        Get or create Rate Dimension ID by name and OrgId.

        Args:
            dimension_name: Name of the Rate Dimension

        Returns:
            Rate Dimension ID if found or created, None otherwise
        """
        self.logger.info(f"Retrieving Rate Dimension ID for: {dimension_name} with OrgId: {self.org_id}")
        try:
            encoded_name = quote(dimension_name)
            query_endpoint = f"/rateDimensions?q=Name='{encoded_name}';OrgId={self.org_id}"
            response, status_code = self.api_client.get(query_endpoint)
            log_api_response(f"Get Rate Dimension by Name: {dimension_name}, OrgId: {self.org_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and response.get("items"):
                dimension_id = int(response["items"][0]["RateDimensionId"])
                self.logger.debug(f"Found Rate Dimension {dimension_name} with ID: {dimension_id} and NumberTier: {response['items'][0].get('NumberTier', 0)}")
                return dimension_id
            # Create new dimension if not found
            payload = {
                "Name": dimension_name,
                "RateDimensionType": "AMOUNT",
                "OrgId": self.org_id
            }
            response, status_code = self.api_client.post("/rateDimensions", payload)
            log_api_response(f"Create Rate Dimension: {dimension_name}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201:
                dimension_id = int(response["RateDimensionId"])
                self.logger.info(f"Created Rate Dimension {dimension_name} with ID: {dimension_id}")
                return dimension_id
            self.logger.error(f"Failed to create Rate Dimension {dimension_name}: {response.get('message', 'No message')}")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving/creating Rate Dimension ID: {e}")
            return None

    def add_dimension_to_rate_table(self, rate_table_id: int, rate_dimension_id: int, rate_table_type: str) -> Optional[int]:
        """
        Add or update a Rate Dimension association with a Rate Table.

        Args:
            rate_table_id: ID of the Rate Table
            rate_dimension_id: ID of the Rate Dimension
            rate_table_type: Type of the rate table (e.g., AMOUNT, PERCENT)

        Returns:
            RateTableDimId if successful, None otherwise
        """
        self.logger.info(f"🔧 Adding Dimension {rate_dimension_id} to Rate Table ID: {rate_table_id} (table type: {rate_table_type})")
        try:
            # Get the rate dimension details to check its OrgId, type, and NumberTier
            dimension_endpoint = f"/rateDimensions/{rate_dimension_id}"
            response, status_code = self.api_client.get(dimension_endpoint)
            log_api_response(f"Get Rate Dimension Details for ID: {rate_dimension_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code != 200:
                self.logger.error(f"❌ Failed to retrieve details for Rate Dimension ID: {rate_dimension_id}. Status: {status_code}, Response: {response}")
                return None
            # Check if response is a list (from a collection) or a single item
            dimension = response if "RateDimensionId" in response else response.get("items", [{}])[0] if response.get("items") else {}
            if not dimension:
                self.logger.error(f"❌ No valid data in response for Rate Dimension ID: {rate_dimension_id}. Response: {response}")
                return None
            dimension_type = dimension.get("RateDimensionType", "AMOUNT").upper()
            dimension_org_id = int(dimension.get("OrgId", 0))
            number_tier = int(dimension.get("NumberTier", 0))
            self.logger.info(f"📊 Rate Dimension {rate_dimension_id}: type={dimension_type}, OrgId={dimension_org_id}, NumberTier={number_tier}, RateTableType={rate_table_type}, self.org_id={self.org_id}")

            # Validate OrgId match (use int comparison to handle str/int mismatches)
            if int(dimension_org_id) != int(self.org_id):
                self.logger.error(f"❌ OrgId mismatch: Rate Dimension OrgId {dimension_org_id} != Rate Table OrgId {self.org_id}")
                return None
            self.logger.info(f"✅ OrgId match confirmed: {dimension_org_id}")

            # Check type compatibility — Rate Dimension type "AMOUNT" is universally
            # compatible with all rate table types (PERCENT, AMOUNT, etc.)
            compatible_types = {"AMOUNT", "PERCENT", "EXPRESSION", "STRING"}
            if dimension_type not in compatible_types or rate_table_type not in compatible_types:
                self.logger.error(f"❌ Incompatible types: Dimension type {dimension_type} vs Table type {rate_table_type}")
                return None
            if dimension_type != rate_table_type and dimension_type != "AMOUNT" and rate_table_type != "AMOUNT":
                self.logger.error(f"❌ Type mismatch: Dimension type {dimension_type} not compatible with Table type {rate_table_type}")
                return None
            self.logger.info(f"✅ Type compatibility confirmed: Dimension={dimension_type}, Table={rate_table_type}")

            # Ensure tiers exist if NumberTier is 0
            if number_tier == 0:
                self.logger.warning(f"No tiers found for Rate Dimension ID: {rate_dimension_id}. Creating tiers from Excel.")
                tiers = self.load_rate_dimension_tiers_from_excel(dimension["Name"])
                if not tiers:
                    self.logger.error(f"No tiers defined in Excel for Rate Dimension: {dimension['Name']}")
                    return None
                if not self.create_rate_dimension_tiers(rate_dimension_id, tiers):
                    self.logger.error(f"Failed to create tiers for Rate Dimension ID: {rate_dimension_id}")
                    return None

            # Check if dimension is already associated
            dimension_list_endpoint = f"{self.rate_table_endpoint}/{rate_table_id}/child/RateTableDimensions"
            response, status_code = self.api_client.get(dimension_list_endpoint)
            log_api_response(f"Get Rate Table Dimensions for Rate Table ID: {rate_table_id}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and "items" in response:
                for dim in response["items"]:
                    if dim["RateDimensionId"] == rate_dimension_id:
                        self.logger.info(f"Dimension {rate_dimension_id} already associated with Rate Table ID: {rate_table_id}")
                        return int(dim["RateTableDimId"])

            # If not associated, create new association
            payload = {
                "RateDimensionId": rate_dimension_id
            }
            response, status_code = self.api_client.post(dimension_list_endpoint, payload)
            log_api_response(f"Add Dimension to Rate Table ID: {rate_table_id}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201:
                self.logger.info(f"Successfully added dimension {rate_dimension_id} to Rate Table ID: {rate_table_id}")
                return int(response["RateTableDimId"])
            self.logger.error(f"Failed to add dimension to Rate Table ID: {rate_table_id}: {response.get('message', 'No message')}")
            return None
        except Exception as e:
            self.logger.error(f"Error adding/updating dimension to Rate Table: {e}")
            return None

    def load_rate_dimension_tiers_from_excel(self, dimension_name: str) -> List[Dict[str, Any]]:
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

    def create_rate_dimension_tiers(self, rate_dimension_id: int, tiers: List[Dict[str, Any]]) -> bool:
        """
        Create Rate Dimension Tiers for a given Rate Dimension.

        Args:
            rate_dimension_id: ID of the Rate Dimension
            tiers: List of tier configurations with ranges

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Creating tiers for Rate Dimension ID: {rate_dimension_id}")
        try:
            endpoint = f"/rateDimensions/{rate_dimension_id}/child/RateDimensionTiers"
            response, status_code = self.api_client.get(endpoint)
            existing_tier_keys = set()
            if status_code == 200 and "items" in response:
                existing_tiers = response["items"]
                existing_tier_keys = {(tier["MinimumAmount"], tier["MaximumAmount"]) for tier in existing_tiers}

            success = True
            for index, tier in enumerate(tiers, start=1):
                tier_key = (tier.get("MinimumAmount", 0), tier.get("MaximumAmount", 1000000))
                if tier_key not in existing_tier_keys:
                    self.logger.info(f"Creating new Tier {index} for Range {tier_key} in Rate Dimension ID: {rate_dimension_id}")
                    tier_payload = {
                        "RateDimensionId": rate_dimension_id,
                        "MinimumAmount": tier.get("MinimumAmount", 0),
                        "MaximumAmount": tier.get("MaximumAmount", 1000000)
                    }
                    response, status_code = self.api_client.post(endpoint, tier_payload)
                    log_api_response(f"Create Rate Dimension Tier: Dimension {rate_dimension_id}, Range {tier_key}",
                                    {"status_code": status_code, "response": response}, self.log_file)
                    if status_code != 201:
                        self.logger.error(f"Failed to create Tier for Range {tier_key} for Dimension {rate_dimension_id}: {response.get('message', 'No message')}")
                        success = False
                else:
                    self.logger.info(f"Tier for Range {tier_key} in Rate Dimension {rate_dimension_id} already exists")
            return success
        except Exception as e:
            self.logger.error(f"Error creating Rate Dimension Tiers: {e}")
            return False

    def get_rate_table_rates(self, rate_table_id: int) -> Dict[Tuple[int, Optional[int]], Dict]:
        """
        Get existing Rate Table Rates.

        Args:
            rate_table_id: ID of the Rate Table

        Returns:
            Dictionary of tier keys to rate details
        """
        self.logger.info(f"Retrieving Rate Table Rates for ID: {rate_table_id}")
        try:
            endpoint = f"{self.rate_table_endpoint}/{rate_table_id}/child/RateTableRates"
            response, status_code = self.api_client.get(endpoint)
            log_api_response(f"Get Rate Table Rates for Rate Table ID: {rate_table_id}", {"status_code": status_code, "response": response}, self.log_file)
            if status_code != 200 or "items" not in response:
                self.logger.warning(f"No rates found for Rate Table ID: {rate_table_id}")
                return {}
            rates = {}
            for item in response["items"]:
                tier_key = (int(item["RateDimension1TierId"]) if item["RateDimension1TierId"] else None,
                           int(item["RateDimension2TierId"]) if item["RateDimension2TierId"] else None)
                rates[tier_key] = {
                    "RateTableRateId": int(item["RateTableRateId"]),
                    "Rate": float(item["Rate"]),
                    "RateDimension1Id": item["RateDimension1Id"],
                    "RateDimension2Id": item["RateDimension2Id"]
                }
            return rates
        except Exception as e:
            self.logger.error(f"Error retrieving Rate Table Rates: {e}")
            return {}

    def create_rate_table_rates(self, rate_table_id: int, rate_table_rates_df: pd.DataFrame, rate_table_name: str) -> bool:
        """
        Create or update Rate Table Rates.

        Args:
            rate_table_id: ID of the Rate Table
            rate_table_rates_df: DataFrame containing rate data
            rate_table_name: Name of the Rate Table

        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Creating Rate Table Rates for Rate Table ID: {rate_table_id}")
        try:
            # Fetch existing rates
            existing_rates = self.get_rate_table_rates(rate_table_id)

            # Fetch existing RateTableDimensions
            dimension_endpoint = f"{self.rate_table_endpoint}/{rate_table_id}/child/RateTableDimensions"
            dimension_response, dimension_status = self.api_client.get(dimension_endpoint)
            if dimension_status != 200:
                self.logger.error(f"Failed to fetch dimensions for Rate Table ID: {rate_table_id}, Status: {dimension_status}")
                return False

            # Load rate tables to get the intended dimension name and table type
            rate_tables_df = self.load_rate_tables()
            rate_table_row = rate_tables_df[rate_tables_df["Rate Table Name"] == rate_table_name].iloc[0]
            intended_dimension_name = rate_table_row.get("Rate Dimension Name", f"{rate_table_name}_Dimension")
            raw_rate_table_type = str(rate_table_row.get("RateTableType", "PERCENT")).strip()
            # Map human-readable names to Oracle API values
            type_mapping = {
                "Amount": "AMOUNT", "Percent": "PERCENT", "Expression": "EXPRESSION",
                "Standard": "PERCENT", "String": "STRING", "Sales": "PERCENT",
            }
            rate_table_type = type_mapping.get(raw_rate_table_type, raw_rate_table_type.upper())

            # Retrieve or create the dimension with the correct OrgId
            intended_rate_dimension_id = self.get_rate_dimension_id(intended_dimension_name)
            if intended_rate_dimension_id is None:
                self.logger.error(f"Rate Dimension {intended_dimension_name} not found for OrgId {self.org_id} and could not be created.")
                return False

            # Ensure the dimension is associated before configuring rates
            if not dimension_response.get("items"):
                self.logger.info(f"No dimensions found for Rate Table ID: {rate_table_id}. Associating {intended_dimension_name}")
                rate_table_dim_id = self.add_dimension_to_rate_table(rate_table_id, intended_rate_dimension_id, rate_table_type)
                if not rate_table_dim_id:
                    self.logger.error(f"Failed to associate dimension {intended_dimension_name} with Rate Table ID: {rate_table_id}")
                    return False
            else:
                self.logger.info(f"Dimensions exist for Rate Table ID: {rate_table_id}. Verifying {intended_dimension_name}")
                existing_dims = {dim["RateDimensionId"] for dim in dimension_response["items"]}
                if intended_rate_dimension_id not in existing_dims:
                    self.logger.warning(f"Intended dimension {intended_dimension_name} not found. Adding it.")
                    rate_table_dim_id = self.add_dimension_to_rate_table(rate_table_id, intended_rate_dimension_id, rate_table_type)
                    if not rate_table_dim_id:
                        self.logger.error(f"Failed to associate dimension {intended_dimension_name}")
                        return False

            # Refresh dimensions
            dimension_response, dimension_status = self.api_client.get(dimension_endpoint)
            if dimension_status != 200 or not dimension_response.get("items"):
                self.logger.error(f"No dimensions after association for Rate Table ID: {rate_table_id}")
                return False
            rate_dimensions = {item["RateDimensionId"]: item["RateTableDimId"] for item in dimension_response["items"]}
            rate_dimension_id = intended_rate_dimension_id
            rate_table_dim_id = rate_dimensions[rate_dimension_id]

            # Ensure tiers exist
            tiers_endpoint = f"/rateDimensions/{rate_dimension_id}/child/RateDimensionTiers"
            tiers_response, tiers_status = self.api_client.get(tiers_endpoint)
            if tiers_status != 200 or "items" not in tiers_response:
                self.logger.warning(f"No tiers found. Creating tiers for Dimension ID: {rate_dimension_id}")
                tiers = self.load_rate_dimension_tiers_from_excel(intended_dimension_name)
                if not tiers:
                    self.logger.error(f"No tiers defined in Excel for Rate Dimension: {intended_dimension_name}")
                    return False
                if not self.create_rate_dimension_tiers(rate_dimension_id, tiers):
                    self.logger.error(f"Failed to create tiers")
                    return False
                tiers_response, tiers_status = self.api_client.get(tiers_endpoint)
            rate_dim1_tiers = {int(tier["TierSequence"]): int(tier["RateDimTierId"]) for tier in tiers_response["items"]}

            # Filter rates for the current table
            rates_for_table = rate_table_rates_df[rate_table_rates_df["Rate Table Name"].str.strip() == rate_table_name].copy()
            self.logger.info(f"Rates for table {rate_table_name}: {rates_for_table.to_dict(orient='records')}")
            if rates_for_table.empty:
                self.logger.warning(f"No rate data for Rate Table: {rate_table_name}")
                return True

            # Create or update rates
            rates_endpoint = f"{self.rate_table_endpoint}/{rate_table_id}/child/RateTableRates"
            for index, rate_row in rates_for_table.iterrows():
                tier_sequence = int(rate_row.get("TierSequence", 1))
                rate_value = float(rate_row.get("RateValue", 0.0))  # Default to 0.0 if not found
                self.logger.debug(f"Processing tier {tier_sequence} with rate_value {rate_value}")
                if pd.isna(rate_value) or rate_value == 0.0:
                    self.logger.warning(f"Skipping rate for Tier {tier_sequence} with invalid or zero value: {rate_value}")
                    continue
                if tier_sequence not in rate_dim1_tiers:
                    self.logger.warning(f"Tier sequence {tier_sequence} not found. Creating default tier.")
                    default_tier = {"MinimumAmount": 0, "MaximumAmount": 1000000}  # Fallback tier
                    if not self.create_rate_dimension_tiers(rate_dimension_id, [default_tier]):
                        self.logger.error(f"Failed to create tier for sequence {tier_sequence}")
                        return False
                    tiers_response, tiers_status = self.api_client.get(tiers_endpoint)
                    rate_dim1_tiers = {int(tier["TierSequence"]): int(tier["RateDimTierId"]) for tier in tiers_response["items"]}
                rate_dim1_tier_id = rate_dim1_tiers[tier_sequence]
                tier_key = (rate_dim1_tier_id, None)
                if tier_key in existing_rates:
                    existing_rate = existing_rates[tier_key]["Rate"]
                    # Temporarily force update for debugging
                    self.logger.info(f"Existing rate for Tier {tier_sequence} is {existing_rate}, new rate is {rate_value}")
                    rate_table_rate_id = existing_rates[tier_key]["RateTableRateId"]
                    update_endpoint = f"{rates_endpoint}/{rate_table_rate_id}"
                    update_payload = {"Rate": rate_value}
                    update_response, update_status = self.api_client.patch(update_endpoint, update_payload)
                    log_api_response(f"Update Rate for Tier {tier_sequence}", {"status_code": update_status, "response": update_response}, self.log_file)
                    if update_status != 200:
                        self.logger.error(f"Failed to update rate for tier {tier_sequence}")
                        return False
                    self.logger.info(f"Updated rate for Tier {tier_sequence} to {rate_value}")
                else:
                    create_payload = {
                        "RateTableId": rate_table_id,
                        "RateDimension1Id": rate_dimension_id,
                        "RateDimension1TierId": rate_dim1_tier_id,
                        "Rate": rate_value
                    }
                    create_response, create_status = self.api_client.post(rates_endpoint, create_payload)
                    log_api_response(f"Create Rate for Tier {tier_sequence}", {"status_code": create_status, "response": create_response}, self.log_file)
                    if create_status != 201:
                        self.logger.error(f"Failed to create rate for tier {tier_sequence}: {create_response.get('message', 'No message')}")
                        return False
                    self.logger.info(f"Created rate for Tier {tier_sequence} with value {rate_value}")
            return True
        except Exception as e:
            self.logger.exception(f"Error creating Rate Table Rates: {e}")
            return False

    def create_rate_tables(self, force: bool = False) -> bool:
        """
        Create or update Rate Tables from Excel.

        Args:
            force: Whether to force creation/update even if errors occur

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("Starting Rate Table creation process")
        try:
            rate_tables_df = self.load_rate_tables()
            rate_table_rates_df = self.load_rate_table_rates()
            success_count = 0
            error_count = 0

            # Map Excel RateTableType to API-compatible values
            rate_table_type_mapping = {
                "Amount": "AMOUNT",
                "Percent": "PERCENT",
                "Expression": "EXPRESSION",
                "Standard": "PERCENT",  # Default mapping for "Standard"
                "String": "STRING"
            }

            for index, row in rate_tables_df.iterrows():
                rate_table_name = row["Rate Table Name"]
                self.logger.info(f"Processing Rate Table: {rate_table_name} with OrgId: {self.org_id}")
                rate_table_id = self.get_rate_table_id(rate_table_name)

                if rate_table_id:
                    self.logger.info(f"Rate Table '{rate_table_name}' exists with ID: {rate_table_id} for OrgId: {self.org_id}")
                    # Patch existing rate table to update attributes if needed
                    excel_rate_table_type = row.get("RateTableType", "Standard")
                    api_rate_table_type = rate_table_type_mapping.get(excel_rate_table_type, "PERCENT")
                    payload = {
                        "DisplayName": row.get("Display Name", rate_table_name),
                        "Description": row.get("Description", "")
                    }
                    if "RateTableType" in row and row["RateTableType"] != "":
                        payload["RateTableType"] = api_rate_table_type
                    response, status_code = self.api_client.patch(f"{self.rate_table_endpoint}/{rate_table_id}", payload)
                    log_api_response(f"Patch Rate Table: {rate_table_name}", {"status_code": status_code, "response": response}, self.log_file)
                    if status_code != 200:
                        self.logger.error(f"Failed to patch Rate Table: {rate_table_name}: {response.get('message', 'No message')}")
                        error_count += 1
                        if not force:
                            return False
                        continue
                else:
                    self.logger.info(f"Creating new Rate Table: {rate_table_name} with OrgId: {self.org_id}")
                    excel_rate_table_type = row.get("RateTableType", "Standard")
                    api_rate_table_type = rate_table_type_mapping.get(excel_rate_table_type, "PERCENT")
                    payload = {
                        "Name": rate_table_name,
                        "OrgId": self.org_id,
                        "RateTableType": api_rate_table_type,
                        "DisplayName": row.get("Display Name", rate_table_name),
                        "Description": row.get("Description", "")
                    }
                    self.logger.debug(f"Payload for creating Rate Table {rate_table_name}: {payload}")
                    response, status_code = self.api_client.post(self.rate_table_endpoint, payload)
                    log_api_response(f"Create Rate Table: {rate_table_name}", {"status_code": status_code, "response": response}, self.log_file)
                    if status_code == 201 and isinstance(response, dict) and "RateTableId" in response:
                        rate_table_id = response["RateTableId"]
                        self.logger.info(f"Successfully created Rate Table: {rate_table_name} with ID: {rate_table_id}")
                    elif status_code == 400:
                        # 400 often means "already exists" — re-check
                        self.logger.warning(f"POST returned 400 for Rate Table '{rate_table_name}'. Re-checking if it exists.")
                        rate_table_id = self.get_rate_table_id(rate_table_name)
                        if rate_table_id:
                            self.logger.info(f"Found existing Rate Table '{rate_table_name}' with ID: {rate_table_id}")
                        else:
                            self.logger.error(f"Rate Table '{rate_table_name}' not found after 400. Cannot proceed.")
                            error_count += 1
                            if not force:
                                return False
                            continue
                    else:
                        self.logger.error(f"Failed to create Rate Table: {rate_table_name}: {response.get('message', 'No message') if isinstance(response, dict) else response}")
                        error_count += 1
                        if not force:
                            return False
                        continue

                if not self.create_rate_table_rates(rate_table_id, rate_table_rates_df, rate_table_name):
                    self.logger.error(f"Failed to configure rates for Rate Table: {rate_table_name}")
                    error_count += 1
                    if not force:
                        return False
                else:
                    success_count += 1

            self.logger.info(f"Rate Table creation completed. {success_count} successful, {error_count} errors.")
            return True if success_count > 0 else False if error_count > 0 else True
        except Exception as e:
            self.logger.exception(f"Error in create_rate_tables: {e}")
            return False