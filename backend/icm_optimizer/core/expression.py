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

            # Normalize column names: the AI-generated workbook uses space-separated
            # names (e.g. "Measure Name") but the code uses camelCase (e.g. "MeasureName").
            # Map common space-separated variants to the expected camelCase names.
            col_mapping = {
                'Expression Detail Type': 'ExpressionDetailType',
                'Expression detail type': 'ExpressionDetailType',
                'Measure Name': 'MeasureName',
                'Measure Result Attribute': 'MeasureResultAttribute',
                'Basic Attributes Group': 'BasicAttributesGroup',
                'Basic Attribute Name': 'BasicAttributeName',
                'Plan Component Name': 'PlanComponentName',
                'Plan Component Result Attribute': 'PlanComponentResultAttribute',
                'Constant Value': 'ConstantValue',
                'Expression Operator': 'ExpressionOperator',
                'Expression Detail ID': 'ExpressionDetailId',
            }
            df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns}, inplace=True)
            self.logger.debug(f"Normalized columns: {df.columns.tolist()}")

            required_cols = ['Expression Name', 'ExpressionDetailType', 'Sequence']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                self.logger.error(f"❌ Missing required columns: {missing_cols}")
                return []

            expressions = {}
            detail_rows_map = {}  # expr_name -> list of ExpressionDetail payloads
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
                    detail_rows_map[expr_name] = []

                detail_type = row.get('ExpressionDetailType', '').strip()
                sequence = pd.to_numeric(row.get('Sequence', 0), errors='coerce')
                if pd.isna(sequence):
                    sequence = 0

                # Build ExpressionDetails child row for the Oracle API.
                #
                # Oracle REST API ExpressionDetailType uses DISPLAY values, NOT internal codes:
                #   "Primary object attribute"   (NOT "PRIMOBJATTR")
                #   "Measure result"             (NOT "MEASURERESULT")
                #   "Plan component result"      (NOT "PLANCOMPRESULT")
                #   "Mathematical operator"      (NOT "MATHOPERATOR")
                #   "Constant"                   (NOT "CONSTANT")
                #   "Rate table rate"            (for RTR lookups)
                #   "SQL expression function"    (for SQL functions)
                #
                # Oracle ExpressionOperator uses symbols, NOT words:
                #   *  (NOT "MULTIPLY")
                #   +  (NOT "ADD")
                #   -  (NOT "SUBTRACT")
                #   /  (NOT "DIVIDE")
                #   (  )  ,  (grouping/function args)

                # Mapping from internal codes / AI labels → Oracle display values
                _DETAIL_TYPE_MAP = {
                    'PRIMOBJATTR': 'Primary object attribute',
                    'MEASURERESULT': 'Measure result',
                    'PLANCOMPRESULT': 'Plan component result',
                    'MATHOPERATOR': 'Mathematical operator',
                    'CONSTANT': 'Constant',
                    'RATETABLERATE': 'Rate table rate',
                    'SQLFUNC': 'SQL expression function',
                    # Also accept Oracle display values as-is
                    'Primary object attribute': 'Primary object attribute',
                    'Measure result': 'Measure result',
                    'Plan component result': 'Plan component result',
                    'Mathematical operator': 'Mathematical operator',
                    'Constant': 'Constant',
                    'Rate table rate': 'Rate table rate',
                    'SQL expression function': 'SQL expression function',
                }
                # Operator word → symbol mapping
                _OPERATOR_MAP = {
                    'MULTIPLY': '*', 'MUL': '*', 'TIMES': '*',
                    'ADD': '+', 'PLUS': '+', 'SUM': '+',
                    'SUBTRACT': '-', 'MINUS': '-',
                    'DIVIDE': '/', 'DIV': '/',
                    # Already-correct symbols pass through
                    '*': '*', '+': '+', '-': '-', '/': '/',
                    '(': '(', ')': ')', ',': ',',
                }

                detail_row = {}

                # Read all possible fields (cleaned of NaN)
                measure_name = row.get('MeasureName', '')
                result_attr = row.get('MeasureResultAttribute', '')
                attr_group = row.get('BasicAttributesGroup', '')
                attr_name = row.get('BasicAttributeName', '')
                pc_name = row.get('PlanComponentName', '')
                pc_attr = row.get('PlanComponentResultAttribute', '')
                operator = row.get('ExpressionOperator', '')
                constant = row.get('ConstantValue', '')
                measure_name = '' if pd.isna(measure_name) else str(measure_name).strip()
                result_attr = '' if pd.isna(result_attr) else str(result_attr).strip()
                attr_group = '' if pd.isna(attr_group) else str(attr_group).strip()
                attr_name = '' if pd.isna(attr_name) else str(attr_name).strip()
                pc_name = '' if pd.isna(pc_name) else str(pc_name).strip()
                pc_attr = '' if pd.isna(pc_attr) else str(pc_attr).strip()
                operator = '' if pd.isna(operator) else str(operator).strip()
                constant = '' if pd.isna(constant) else str(constant).strip()

                # Normalize operator words → symbols
                if operator:
                    operator = _OPERATOR_MAP.get(operator.upper(), _OPERATOR_MAP.get(operator, operator))

                # Resolve the Oracle display-value for ExpressionDetailType
                oracle_type = _DETAIL_TYPE_MAP.get(detail_type, None)

                # If detail_type is a generic AI label (Calculation, Formula, etc.),
                # infer the correct Oracle type from the available column data.
                if not oracle_type:
                    if measure_name and result_attr:
                        oracle_type = 'Measure result'
                    elif attr_group and attr_name:
                        oracle_type = 'Primary object attribute'
                    elif pc_name and pc_attr:
                        oracle_type = 'Plan component result'
                    elif operator:
                        oracle_type = 'Mathematical operator'
                    elif constant:
                        oracle_type = 'Constant'

                seq = int(sequence) if sequence > 0 else len(detail_rows_map[expr_name]) + 1

                if oracle_type == 'Measure result' and measure_name and result_attr:
                    expressions[expr_name]['Expression'] = f"{measure_name}.{result_attr}"
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                        "MeasureName": measure_name,
                        "MeasureResultAttribute": result_attr,
                    }
                elif oracle_type == 'Primary object attribute' and attr_group and attr_name:
                    expressions[expr_name]['Expression'] = f"{attr_group}.{attr_name}"
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                        "BasicAttributesGroup": attr_group,
                        "BasicAttributeName": attr_name,
                    }
                elif oracle_type == 'Plan component result' and pc_name and pc_attr:
                    expressions[expr_name]['Expression'] = f"{pc_name}.{pc_attr}"
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                        "PlanComponentName": pc_name,
                        "PlanComponentResultAttribute": pc_attr,
                    }
                elif oracle_type == 'Mathematical operator' and operator:
                    expressions[expr_name]['Expression'] += f" {operator} "
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                        "ExpressionOperator": operator,
                    }
                elif oracle_type == 'Constant' and constant:
                    expressions[expr_name]['Expression'] += constant
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                        "ConstantValue": constant,
                    }
                elif oracle_type == 'Rate table rate':
                    expressions[expr_name]['Expression'] += 'RTR'
                    detail_row = {
                        "ExpressionDetailType": oracle_type,
                        "Sequence": seq,
                    }
                else:
                    # Fallback: no structured detail rows — set expression text from description
                    desc = row.get('Description', '')
                    if desc and not pd.isna(desc) and str(desc).strip():
                        expressions[expr_name]['Expression'] = str(desc).strip()
                    else:
                        expressions[expr_name]['Expression'] = expr_name

                if detail_row:
                    detail_rows_map[expr_name].append(detail_row)

                if expressions[expr_name]['Expression'] and sequence > 0:
                    expressions[expr_name]['Expression'] = expressions[expr_name]['Expression'].strip()

            # Attach detail rows to each expression for ExpressionDetails API
            for expr_name, expr in expressions.items():
                expr['_detail_rows'] = detail_rows_map.get(expr_name, [])

            result = [expr for expr in expressions.values() if expr['Expression']]
            if not result:
                self.logger.warning("⚠ No valid expressions found after processing")
                return []

            self.logger.info(f"✅ Loaded {len(result)} expressions: {result}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error loading Expressions: {str(e)}")
            return []

    def _extract_uniq_id(self, expression_item: Dict[str, Any]) -> Optional[str]:
        """Extract the incentiveCompensationExpressionsUniqID from the self link.

        Oracle REST API requires this UniqID (not ExpressionId) in PATCH/GET-by-key
        URLs:  .../incentiveCompensationExpressions/{uniqId}
        """
        for link in expression_item.get("links", []):
            if link.get("rel") == "self":
                href = link.get("href", "")
                # href ends with .../incentiveCompensationExpressions/{uniqId}
                parts = href.rstrip("/").split("/")
                if parts:
                    return parts[-1]
        return None

    def get_expression_details(self, expression_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Expression details by name, scoped to the current OrgId.

        Args:
            expression_name: Name of the Expression

        Returns:
            Expression details dict (includes _uniq_id key) if found, None otherwise
        """
        self.logger.info(f"🔍 Retrieving Expression details for: {expression_name}")
        try:
            encoded_name = quote(expression_name)
            endpoint = f"{self.expression_endpoint}?q=Name='{encoded_name}';OrgId={self.org_id}"
            response, status_code = self.api_client.get(endpoint)
            log_api_response(f"Get Expression by Name: {expression_name}",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200 and response.get("items"):
                expression_details = response["items"][0]
                # Attach the UniqID for PATCH operations
                uniq_id = self._extract_uniq_id(expression_details)
                expression_details["_uniq_id"] = uniq_id
                self.logger.info(f"✅ Found Expression '{expression_name}' with ID: {expression_details['ExpressionId']}, UniqID: {uniq_id}")
                return expression_details
            self.logger.info(f"⚠ Expression '{expression_name}' not found.")
            return None
        except Exception as e:
            self.logger.error(f"❌ Error retrieving Expression details for '{expression_name}': {e}")
            return None

    def _patch_expression(self, uniq_id: str, expression_name: str,
                          payload: Dict[str, Any]) -> bool:
        """PATCH an expression using its UniqID (not ExpressionId).

        Oracle requires the composite hash key (UniqID) from the self link,
        NOT the numeric ExpressionId, in the URL path:
            .../incentiveCompensationExpressions/{uniqId}

        Oracle PATCH writable fields (per API schema):
          - Name (string)
          - Description (string)
          - ExpressionDetails (array) — inline child detail rows
          - ExpressionUsages (array) — inline child usage rows

        Read-only fields (will cause 400 "Unable to parse the provided payload"):
          - Expression, ExpressionType, ExpressionId, OrgId, Status,
            CreatedBy, CreationDate, LastUpdateDate, LastUpdatedBy, etc.
        """
        # Filter payload to only Oracle-accepted PATCH fields
        allowed_fields = {"Name", "Description", "ExpressionDetails", "ExpressionUsages"}
        safe_payload = {k: v for k, v in payload.items() if k in allowed_fields}
        if not safe_payload:
            self.logger.info(f"ℹ No PATCH-able fields for Expression '{expression_name}'. Skipping PATCH.")
            return True

        endpoint = f"{self.expression_endpoint}/{uniq_id}"
        response, status_code = self.api_client.patch(endpoint, safe_payload)
        log_api_response(f"PATCH Expression: {expression_name}",
                        {"status_code": status_code, "response": response}, self.log_file)
        if status_code == 200:
            self.logger.info(f"✅ PATCHed Expression '{expression_name}' via UniqID {uniq_id}")
            return True
        self.logger.warning(f"⚠ PATCH returned {status_code} for Expression '{expression_name}': {response}")
        return False

    def _set_expression_details(self, uniq_id: str, expression_name: str,
                                detail_rows: List[Dict[str, Any]],
                                description: str = "",
                                force_replace: bool = False) -> bool:
        """Set expression formula via inline ExpressionDetails in a single PATCH.

        Oracle API supports inline ExpressionDetails in the PATCH payload:
            PATCH .../incentiveCompensationExpressions/{uniqId}
            {
              "Description": "...",
              "ExpressionDetails": [
                {"ExpressionDetailType": "PRIMOBJATTR", "Sequence": 1, ...},
                {"ExpressionDetailType": "MATHOPERATOR", "Sequence": 2, ...}
              ]
            }

        This is the most efficient approach — a single API call sets both
        metadata and all formula components at once.

        Fallback: If inline PATCH fails, falls back to individual
        POST/PATCH calls on the child ExpressionDetails endpoint.

        Args:
            uniq_id: The incentiveCompensationExpressionsUniqID
            expression_name: Human-readable name for logging
            detail_rows: List of ExpressionDetail payloads
            description: Optional description to set alongside details
            force_replace: If True, update even when details already exist
        """
        # Check if details already exist
        child_endpoint = f"{self.expression_endpoint}/{uniq_id}/child/ExpressionDetails"
        existing_resp, existing_status = self.api_client.get(child_endpoint)
        existing_items = existing_resp.get("items", []) if existing_status == 200 else []

        if existing_items and not force_replace:
            self.logger.info(f"✅ ExpressionDetails already exist for '{expression_name}' ({len(existing_items)} rows). Skipping.")
            return True

        # Clean detail rows (remove None/empty values)
        clean_details = []
        for detail in detail_rows:
            clean_detail = {k: v for k, v in detail.items() if v is not None and v != ''}
            if clean_detail:
                clean_details.append(clean_detail)

        # Update description via PATCH if provided (description-only PATCH works)
        if description:
            self._patch_expression(uniq_id, expression_name, {"Description": description})

        if existing_items and force_replace:
            # PATCH existing detail rows by ExpressionDetailId
            self.logger.info(f"🔄 Updating {len(existing_items)} existing ExpressionDetails for '{expression_name}' via individual PATCH.")
            success = True
            # Oracle treats 'Sequence' as read-only on PATCH updates
            # (400 "Sequence: Attribute Sequence cannot be set").
            # Exclude it from PATCH payloads — it was set when the detail was created.
            _PATCH_READONLY_FIELDS = {"Sequence"}
            for idx, existing_detail in enumerate(existing_items):
                detail_id = existing_detail.get("ExpressionDetailId")
                if not detail_id:
                    continue
                if idx < len(detail_rows):
                    patch_payload = {k: v for k, v in detail_rows[idx].items()
                                     if v is not None and v != '' and k not in _PATCH_READONLY_FIELDS}
                    patch_endpoint = f"{child_endpoint}/{detail_id}"
                    response, status_code = self.api_client.patch(patch_endpoint, patch_payload)
                    log_api_response(f"PATCH ExpressionDetail #{idx+1} (ID:{detail_id}) for '{expression_name}'",
                                    {"status_code": status_code, "response": response}, self.log_file)
                    if status_code == 200:
                        self.logger.info(f"✅ PATCHed ExpressionDetail #{idx+1} for '{expression_name}'")
                    else:
                        self.logger.warning(f"⚠ PATCH ExpressionDetail #{idx+1} failed for '{expression_name}': {status_code}")
                        success = False
            # POST any additional new rows beyond existing count
            for idx in range(len(existing_items), len(detail_rows)):
                detail_payload = {k: v for k, v in detail_rows[idx].items()
                                 if v is not None and v != ''}
                response, status_code = self.api_client.post(child_endpoint, detail_payload)
                log_api_response(f"Create ExpressionDetail #{idx+1} for '{expression_name}'",
                                {"status_code": status_code, "response": response}, self.log_file)
                if status_code not in [200, 201]:
                    self.logger.warning(f"⚠ ExpressionDetail #{idx+1} POST failed for '{expression_name}': {status_code}")
                    success = False
            return success

        # No existing details — POST all new rows individually
        success = True
        for idx, detail in enumerate(detail_rows, start=1):
            detail_payload = {k: v for k, v in detail.items() if v is not None and v != ''}
            response, status_code = self.api_client.post(child_endpoint, detail_payload)
            log_api_response(f"Create ExpressionDetail #{idx} for '{expression_name}'",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code not in [200, 201]:
                self.logger.warning(f"⚠ ExpressionDetail #{idx} failed for '{expression_name}': {status_code}")
                success = False
        return success

    def validate_expression(self, expression_name: str) -> bool:
        """Check if an expression has Status=VALID and is ready for assignment.

        Oracle auto-validates expressions when their ExpressionDetails are
        syntactically correct.  An expression with Status=INVALID cannot be
        assigned to an Incentive Formula (the PATCH will return 400
        "The value of the attribute OutputExpId isn't valid").

        Returns True if the expression is VALID, False otherwise.
        """
        details = self.get_expression_details(expression_name)
        if not details:
            self.logger.warning(f"⚠ Cannot validate expression '{expression_name}': not found.")
            return False

        status = details.get("Status", "INVALID")
        expr_id = details.get("ExpressionId")
        if status == "VALID":
            self.logger.info(f"✅ Expression '{expression_name}' (ID:{expr_id}) Status=VALID — ready for assignment.")
            return True

        self.logger.warning(
            f"⚠ Expression '{expression_name}' (ID:{expr_id}) Status={status}. "
            "It must be VALID before it can be assigned to an Incentive Formula. "
            "Ensure ExpressionDetails are correctly set."
        )
        return False

    def get_expression_status(self, expression_name: str) -> str:
        """Return the Status field of an expression ('VALID', 'INVALID', or empty)."""
        details = self.get_expression_details(expression_name)
        if not details:
            return ""
        return details.get("Status", "INVALID")

    def _check_expression_usages(self, uniq_id: str, expression_name: str) -> bool:
        """Check Expression Usages to verify an expression is valid.

        Oracle auto-creates ExpressionUsages for valid expressions.
        GET .../incentiveCompensationExpressions/{uniqId}/child/ExpressionUsages

        Returns:
            True if the expression has usages (is valid), False otherwise.
            Note: A newly created expression may not have usages yet until it's
            fully configured with details — this is informational, not blocking.
        """
        endpoint = f"{self.expression_endpoint}/{uniq_id}/child/ExpressionUsages"
        try:
            response, status_code = self.api_client.get(endpoint)
            log_api_response(f"Check ExpressionUsages for '{expression_name}'",
                            {"status_code": status_code, "response": response}, self.log_file)
            if status_code == 200:
                items = response.get("items", [])
                if items:
                    usage_types = [u.get("UsageType", "unknown") for u in items]
                    self.logger.info(f"✅ Expression '{expression_name}' is valid with {len(items)} usage(s): {usage_types}")
                    return True
                else:
                    self.logger.info(f"ℹ Expression '{expression_name}' has no usages yet (may need details or validation).")
                    return False
            else:
                self.logger.warning(f"⚠ Could not check usages for '{expression_name}': status {status_code}")
                return False
        except Exception as e:
            self.logger.warning(f"⚠ Error checking ExpressionUsages for '{expression_name}': {e}")
            return False

    def _build_expression_detail_rows(self, expression: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build ExpressionDetails rows from the loaded expression data.

        Returns the structured detail rows (PRIMOBJATTR, MEASURERESULT, MATHOPERATOR,
        CONSTANT, PLANCOMPRESULT) parsed from the Excel during load_expressions().
        If no structured detail rows are available, returns empty list — the expression
        will be created as a shell only (formula must be set manually or via UI).
        """
        # Check if we have the original DataFrame rows with detail types
        # These are stored during load_expressions if detail_type info is available
        if "_detail_rows" in expression and expression["_detail_rows"]:
            return expression["_detail_rows"]
        return []

    def create_or_update_expression(self, expression: Dict[str, Any]) -> Optional[int]:
        """
        Create or update an Expression if it doesn't match the expected configuration.

        Strategy:
        1. Check if expression exists by name (scoped to OrgId).
        2. If exists and formula matches: skip (idempotent).
        3. If exists and formula differs: PATCH with Description + inline
           ExpressionDetails array (single API call for metadata + formula).
        4. If not exists: POST shell (Name+OrgId+Description), then
           PATCH with inline ExpressionDetails to set formula.

        Oracle REST API key facts (from schema):
        - POST creates shell: Name, OrgId, Description.
        - PATCH writable fields: Name, Description, ExpressionDetails (array),
          ExpressionUsages (array).
        - Read-only fields (400 if sent via PATCH): Expression, ExpressionType,
          ExpressionId, OrgId, Status, CreatedBy, CreationDate, etc.
        - ExpressionDetails can be sent inline in PATCH payload as an array,
          OR individually via POST/PATCH on .../child/ExpressionDetails.
        - ExpressionType defaults to CALCULATION; Status defaults to INVALID.
        - PATCH and GET-by-key require UniqID (from self link), NOT ExpressionId.

        Args:
            expression: Dictionary with Name, OrgId, Expression, ExpressionType, Description

        Returns:
            ExpressionId if created or updated, None if failed
        """
        expression_name = expression["Name"]
        expected_expression_value = expression.get("Expression", "")
        org_id = int(expression.get("OrgId", self.org_id))
        description = expression.get("Description", expression_name)

        self.logger.info(f"🔧 Processing Expression: {expression_name}")

        # ── Check if already exists ──────────────────────────
        existing_expression = self.get_expression_details(expression_name)
        if existing_expression:
            expression_id = existing_expression["ExpressionId"]
            uniq_id = existing_expression.get("_uniq_id")
            current_expression_value = existing_expression.get("Expression", "")

            status = existing_expression.get("Status", "INVALID")
            if current_expression_value == expected_expression_value and status == "VALID":
                self.logger.info(f"✅ Expression '{expression_name}' already matches and Status=VALID. Skipping.")
                return expression_id

            if current_expression_value == expected_expression_value and status != "VALID":
                # Formula text matches but expression is INVALID — ExpressionDetails
                # were likely not set correctly.  Force re-set them.
                self.logger.warning(
                    f"⚠ Expression '{expression_name}' text matches but Status={status}. "
                    "Re-setting ExpressionDetails to fix validation."
                )
                if uniq_id:
                    detail_rows = self._build_expression_detail_rows(expression)
                    if detail_rows:
                        self._set_expression_details(
                            uniq_id, expression_name, detail_rows,
                            description=description, force_replace=True,
                        )
                    else:
                        self.logger.warning(f"⚠ No detail rows available for '{expression_name}'. Cannot fix INVALID status.")
                return expression_id

            # Expression exists but formula differs — update via single PATCH
            if uniq_id and expected_expression_value:
                self.logger.info(f"⚠ Expression '{expression_name}' differs. Updating via UniqID {uniq_id}.")
                detail_rows = self._build_expression_detail_rows(expression)
                if detail_rows:
                    self._set_expression_details(uniq_id, expression_name, detail_rows,
                                                 description=description, force_replace=True)
                else:
                    # No structured detail rows — just update Description
                    self._patch_expression(uniq_id, expression_name, {"Description": description})
                    self.logger.info(f"ℹ No ExpressionDetail rows for '{expression_name}'. Only Description updated.")

                return expression_id
            else:
                self.logger.warning(f"⚠ No UniqID for Expression '{expression_name}'. Returning existing ID.")
                return expression_id

        # ── Create new expression ────────────────────────────
        self.logger.info(f"⚠ Expression '{expression_name}' does not exist. Creating shell.")
        create_payload = {
            "Name": expression_name,
            "OrgId": org_id,
            "Description": description,
        }
        try:
            response, status_code = self.api_client.post(self.expression_endpoint, create_payload)
            log_api_response(f"Create Expression: {expression_name}",
                           {"status_code": status_code, "response": response}, self.log_file)

            if status_code == 201 and isinstance(response, dict) and "ExpressionId" in response:
                expression_id = response["ExpressionId"]
                uniq_id = self._extract_uniq_id(response)
                self.logger.info(f"✅ Created Expression '{expression_name}' ID: {expression_id}, UniqID: {uniq_id}")

                # Set formula via inline ExpressionDetails in PATCH (single call)
                if uniq_id and expected_expression_value:
                    detail_rows = self._build_expression_detail_rows(expression)
                    if detail_rows:
                        self._set_expression_details(uniq_id, expression_name, detail_rows,
                                                     description=description)
                    else:
                        self.logger.info(f"ℹ No ExpressionDetail rows for '{expression_name}'. Expression created as shell only.")

                    # Check Expression Usages to verify validity
                    self._check_expression_usages(uniq_id, expression_name)
                return expression_id

            # Shell creation returned 400 — likely already exists (race condition or re-run)
            if status_code == 400:
                self.logger.warning(f"⚠ Shell create returned 400 for '{expression_name}'. Re-checking.")
                re_check = self.get_expression_details(expression_name)
                if re_check:
                    expression_id = re_check["ExpressionId"]
                    uniq_id = re_check.get("_uniq_id")
                    self.logger.info(f"✅ Found existing Expression '{expression_name}' ID: {expression_id}")
                    # Update formula via ExpressionDetails if needed
                    current_value = re_check.get("Expression", "")
                    if uniq_id and current_value != expected_expression_value and expected_expression_value:
                        detail_rows = self._build_expression_detail_rows(expression)
                        if detail_rows:
                            self._set_expression_details(uniq_id, expression_name, detail_rows,
                                                         description=description, force_replace=True)
                    return expression_id

            self.logger.error(f"❌ Failed to create Expression '{expression_name}'. Status: {status_code}")
            self.logger.error(f"❌ Response: {response}")
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