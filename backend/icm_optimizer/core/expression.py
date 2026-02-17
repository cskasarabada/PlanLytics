"""
Expression Manager for Oracle ICM Plan Configuration Optimizer.
Handles creation and management of Expressions.
"""
import os
import logging
import pandas as pd
from typing import Optional, Dict, Any, List
from urllib.parse import quote

from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager
from ..utils.logging_utils import log_api_response

# app/core/expression.py
import os
import logging
from typing import Optional
from ..utils.api_client import APIClient
from ..config.config_manager import ConfigManager

class ExpressionManager:
    def __init__(self, api_client: APIClient, config_manager: ConfigManager, log_file: str, excel_path: Optional[str] = None):
        self.api_client = api_client
        self.config_manager = config_manager
        self.log_file = log_file
        self.excel_path = excel_path
        self.logger = logging.getLogger(__name__)

        # Define the expression endpoint for Oracle ICM API
        self.expression_endpoint = "/fscmRestApi/resources/11.13.18.05/incentiveCompensationExpressions"

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

    def configure_expressions(self, force: bool = False) -> bool:
        """Configure expressions based on the Excel file."""
        if not self.excel_path:
            self.logger.error("No Excel file provided for expressions")
            return False
        self.logger.info(f"Configuring expressions from {self.excel_path} for org_id: {self.org_id}")
        # Add your logic here to process the Excel file and configure expressions
        # Example: Simulate creating expressions
        try:
            expressions = [
                {"name": "Expression 1", "expression": "SUM(TransactionAmount)"},
                {"name": "Expression 2", "expression": "AVG(TransactionAmount)"}
            ]
            created_expressions = 0
            for expr in expressions:
                name = expr["name"]
                expression = expr["expression"]
                # Check if the expression already exists
                query = f"{self.expression_endpoint}?q=Name='{name}';OrgId={self.org_id}"
                response, status_code = self.api_client.get(query)
                if status_code == 200 and response.get('items'):
                    self.logger.info(f"Skipping duplicate Expression: {name}")
                    continue
                # Create a new expression
                payload = {
                    "Name": name,
                    "Expression": expression,
                    "OrgId": self.org_id
                }
                response, status_code = self.api_client.post(self.expression_endpoint, data=payload)
                if status_code == 201:
                    created_expressions += 1
                    self.logger.info(f"Successfully created Expression: {name}")
                else:
                    self.logger.error(f"Failed to create Expression: {name}, Status Code: {status_code}, Response: {response}")
                    return False
            self.logger.info(f"Created {created_expressions} Expressions")
            return True
        except Exception as e:
            self.logger.error(f"Error in configure_expressions: {str(e)}")
            return False

    def load_expressions(self) -> List[Dict[str, Any]]:
        """
        Load Expressions from Excel file, handling multi-row expression definitions.

        Returns:
            List of expression configurations
        """
        try:
            self.logger.info(f"📄 Loading Expressions from {self.excel_path}")
            xls = pd.ExcelFile(self.excel_path)
            sheet_names = [name.lower() for name in xls.sheet_names]
            target_sheet = None

            possible_names = ['expression', 'expressions']
            for name in possible_names:
                if name in sheet_names:
                    target_sheet = xls.sheet_names[sheet_names.index(name)]
                    break

            if not target_sheet:
                self.logger.error(f"❌ Worksheet named 'Expression' or 'Expressions' not found. Available sheets: {xls.sheet_names}")
                return []

            self.logger.info(f"Found sheet '{target_sheet}' for Expressions")
            df = pd.read_excel(self.excel_path, sheet_name=target_sheet, dtype=str)
            if df.empty:
                self.logger.error("❌ Expressions sheet is empty")
                return []

            self.logger.debug(f"Initial DataFrame columns: {df.columns.tolist()}")
            self.logger.debug(f"Initial DataFrame head:\n{df.head().to_string()}")

            required_cols = ['Expression Name', 'ExpressionDetailType', 'Sequence']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"❌ Missing required columns: {missing_cols}")
                return []

            expressions = {}
            for _, row in df.iterrows():
                expr_name = row.get('Expression Name')
                if pd.isna(expr_name):
                    continue

                if expr_name not in expressions:
                    expressions[expr_name] = {
                        'Name': expr_name,
                        'Description': row.get('Description', expr_name),
                        'Expression': '',
                        'ExpressionType': 'FORMULA',
                        'OrgId': self.org_id
                    }

                detail_type = row.get('ExpressionDetailType', '').strip()
                sequence = pd.to_numeric(row.get('Sequence', 0), errors='coerce')
                if pd.isna(sequence):
                    sequence = 0

                if detail_type == 'Primary object attribute':
                    attr_group = row.get('BasicAttributesGroup', '')
                    attr_name = row.get('BasicAttributeName', '')
                    if attr_group and attr_name:
                        expressions[expr_name]['Expression'] = f"{attr_group}.{attr_name}"
                elif detail_type == 'Measure result':
                    measure_name = row.get('MeasureName', '')
                    result_attr = row.get('MeasureResultAttribute', '')
                    if measure_name and result_attr:
                        expressions[expr_name]['Expression'] = f"{measure_name}.{result_attr}"
                elif detail_type == 'Math operator':
                    operator = row.get('ExpressionOperator', '')
                    if operator:
                        expressions[expr_name]['Expression'] += f" {operator} "
                elif detail_type == 'Constant':
                    constant = row.get('ConstantValue', '')
                    if constant and constant.strip():
                        expressions[expr_name]['Expression'] += constant.strip()

                if expressions[expr_name]['Expression'] and sequence > 0:
                    expressions[expr_name]['Expression'] = expressions[expr_name]['Expression'].strip()

            result = [expr for expr in expressions.values() if expr['Expression']]
            if not result:
                self.logger.warning("⚠ No valid expressions found after processing")
                return []

            self.logger.info(f"✅ Loaded {len(result)} expressions: {result}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error loading Expressions: {str(e)}")
            return []

    def get_expression_details(self, expression_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Expression details by name.

        Args:
            expression_name: Name of the Expression

        Returns:
            Expression details if found, None otherwise
        """
        self.logger.info(f"🔍 Retrieving Expression details for: {expression_name}")
        try:
            encoded_name = quote(expression_name)
            endpoint = f"{self.expression_endpoint}?q=Name='{encoded_name}'"
            response, status_code = self.api_client.get(endpoint)
            log_api_response(f"Get Expression by Name: {expression_name}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and response.get("items"):
                expression_details = response["items"][0]
                self.logger.info(f"✅ Found Expression '{expression_name}' with ID: {expression_details['ExpressionId']}")
                return expression_details
            self.logger.info(f"⚠ Expression '{expression_name}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"❌ Error retrieving Expression details for '{expression_name}': {e}")
            return None

    def create_or_update_expression(self, expression: Dict[str, Any]) -> Optional[int]:
        """
        Create or update an Expression if it doesn't match the expected configuration.

        Args:
            expression: Dictionary containing expression configuration (Name, OrgId, Expression, ExpressionType)

        Returns:
            Expression ID if created or updated, None if failed
        """
        expression_name = expression["Name"]
        expected_expression_value = expression.get("Expression", "Credit.Credit Amount + 100")
        org_id = int(expression.get("OrgId", self.org_id))
        expression_type = expression.get("ExpressionType", "FORMULA")
        description = expression.get("Description", expression_name)

        self.logger.info(f"🔧 Processing Expression: {expression_name}")
        existing_expression = self.get_expression_details(expression_name)
        if existing_expression:
            current_expression_value = existing_expression.get("Expression", "")
            if current_expression_value == expected_expression_value:
                self.logger.info(f"✅ Expression '{expression_name}' already matches expected value '{expected_expression_value}'. Skipping update.")
                return existing_expression["ExpressionId"]

            self.logger.info(f"⚠ Expression '{expression_name}' differs from expected value. Updating.")
            expression_id = existing_expression["ExpressionId"]
            endpoint = f"{self.expression_endpoint}/{expression_id}"
            payload = {
                "Expression": expected_expression_value,
                "ExpressionType": expression_type,
                "Description": description
            }
            try:
                response, status_code = self.api_client.patch(endpoint, payload)
                log_api_response(f"Update Expression: {expression_name}",
                               {"status_code": status_code, "response": response}, self.log_file)
                if status_code == 200:
                    self.logger.info(f"✅ Successfully updated Expression '{expression_name}' with ID: {expression_id}")
                    return expression_id
                elif status_code == 404:
                    self.logger.warning(f"⚠ Expression '{expression_name}' (ID: {expression_id}) not found or not modifiable. Skipping update.")
                    return expression_id  # Return existing ID to continue
                else:
                    self.logger.error(f"❌ Failed to update Expression '{expression_name}'. Status code: {status_code}")
                    self.logger.error(f"❌ Response details: {response}")
                    return None
            except Exception as e:
                self.logger.error(f"❌ Error updating Expression '{expression_name}': {e}")
                return None

        self.logger.info(f"⚠ Expression '{expression_name}' does not exist. Creating.")
        payload = {
            "Name": expression_name,
            "OrgId": org_id,
            "Expression": expected_expression_value,
            "ExpressionType": expression_type,
            "Description": description
        }
        try:
            response, status_code = self.api_client.post(self.expression_endpoint, payload)
            log_api_response(f"Create Expression: {expression_name}",
                           {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 201 and "ExpressionId" in response:
                expression_id = response["ExpressionId"]
                self.logger.info(f"✅ Successfully created Expression '{expression_name}' with ID: {expression_id}")
                return expression_id
            else:
                self.logger.error(f"❌ Failed to create Expression '{expression_name}'. Status code: {status_code}")
                self.logger.error(f"❌ Response details: {response}")
                return None
        except Exception as e:
            self.logger.error(f"❌ Error creating Expression '{expression_name}': {e}")
            return None

    def configure_expressions(self, force: bool = False) -> bool:
        """
        Configure Expressions from Excel.

        Args:
            force: Whether to continue on error

        Returns:
            True if successful, False otherwise
        """
        self.logger.info("🔧 Starting Expression configuration process")
        try:
            expressions = self.load_expressions()
            if not expressions:
                self.logger.warning("⚠ No expressions to process. Check Excel data.")
                return False

            self.logger.info(f"📄 Loaded {len(expressions)} Expressions from Excel")
            created_or_updated_expressions = 0
            for expression in expressions:
                expression_name = expression["Name"]
                self.logger.info(f"🔧 Processing Expression: {expression_name}")
                expression_id = self.create_or_update_expression(expression)
                if expression_id:
                    created_or_updated_expressions += 1
                    self.logger.info(f"✅ Processed Expression '{expression_name}' with ID: {expression_id}")
                else:
                    self.logger.error(f"❌ Failed to process Expression '{expression_name}'. Skipping.")
                    if not force:
                        return False

            self.logger.info("✅ Expression processing completed!")
            self.logger.info(f"📊 Processed Expressions: {created_or_updated_expressions}")
            return True if created_or_updated_expressions > 0 or len(expressions) > 0 else False
        except Exception as e:
            self.logger.error(f"❌ Error in configure_expressions: {e}")
            return False