"""
Validation utilities for Oracle ICM Plan Configuration Optimizer.
"""

import os
import logging
import requests
import json
import pandas as pd
from typing import Dict, Any, List

# Set up module logger
logger = logging.getLogger(__name__)

def inspect_excel_file(excel_path: str) -> Dict[str, Any]:
    """
    Inspect an Excel file and return detailed information.
    
    Args:
        excel_path (str): Path to the Excel file
    
    Returns:
        Dict containing Excel file details
    """
    # Check if file exists
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found: {excel_path}")
        return {
            "success": False,
            "message": f"File not found: {excel_path}"
        }
    
    try:
        # Read Excel file
        xls = pd.ExcelFile(excel_path)
        
        # Prepare sheet details
        sheet_details = []
        for sheet_name in xls.sheet_names:
            try:
                # Read sheet
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
                
                # Convert numeric/datetime columns to string for JSON serialization
                sample_data = df.head(1).apply(lambda x: x.apply(lambda val: str(val) if not pd.isna(val) else None)).to_dict(orient='records')
                
                # Prepare sheet information
                sheet_info = {
                    "name": sheet_name,
                    "columns": df.columns.tolist(),
                    "column_types": {col: str(df[col].dtype) for col in df.columns},
                    "total_rows": len(df),
                    "sample_data": sample_data
                }
                sheet_details.append(sheet_info)
            
            except Exception as sheet_error:
                logger.warning(f"Error reading sheet {sheet_name}: {str(sheet_error)}")
                sheet_details.append({
                    "name": sheet_name,
                    "error": str(sheet_error)
                })
        
        return {
            "success": True,
            "file_path": excel_path,
            "sheets": sheet_details
        }
    
    except Exception as e:
        logger.error(f"Error inspecting Excel file: {str(e)}")
        return {
            "success": False,
            "message": str(e)
        }

def validate_oracle_api_authentication(base_url, username, password, endpoint=''):
    """
    Enhanced Oracle API authentication validation with comprehensive logging.
    """
    logger.info(f"Attempting to validate Oracle API credentials for {username} at {base_url}")
    
    try:
        # Construct the full URL for the test request
        test_url = base_url
        if endpoint:
            test_url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        logger.debug(f"Constructed Test URL: {test_url}")
        
        # Prepare headers with Basic Auth
        import base64
        auth_string = f"{username}:{password}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {auth_b64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Debug logging of request details
        logger.debug(f"Request Headers: {json.dumps(headers, indent=2)}")
        
        # Make a simple GET request to test authentication
        response = requests.get(
            test_url,
            headers=headers,
            timeout=30  # 30-second timeout
        )
        
        # Extensive logging of response
        logger.debug(f"Response Status Code: {response.status_code}")
        logger.debug(f"Response Headers: {response.headers}")
        
        # Log raw response content for debugging
        try:
            response_text = response.text
            logger.debug(f"Raw Response Content: {response_text[:1000]}...")  # First 1000 chars
        except Exception as text_error:
            logger.error(f"Error capturing response text: {text_error}")
        
        # Attempt to parse JSON, with explicit error logging
        try:
            response_json = response.json()
            logger.debug(f"Parsed Response JSON: {json.dumps(response_json, indent=2)}")
        except json.JSONDecodeError as json_error:
            logger.error(f"JSON Decode Error: {json_error}")
            logger.error(f"Response content that failed to parse: {response.text}")
            return {
                'success': False,
                'message': 'Failed to parse API response',
                'details': {
                    'status_code': response.status_code,
                    'raw_content': response.text,
                    'json_error': str(json_error)
                }
            }
        
        # Complete validation logic
        if 200 <= response.status_code < 300:
            logger.info(f"API authentication successful with status code: {response.status_code}")
            return {
                'success': True,
                'message': 'API authentication successful',
                'details': {
                    'status_code': response.status_code,
                    'response': response_json if isinstance(response_json, dict) else {'response': 'Valid but not JSON object'}
                }
            }
        elif response.status_code == 401:
            logger.warning(f"API authentication failed: Unauthorized (status code: 401)")
            return {
                'success': False,
                'message': 'Authentication failed: Invalid credentials',
                'details': {
                    'status_code': 401,
                    'error': 'Unauthorized'
                }
            }
        elif response.status_code == 403:
            logger.warning(f"API authentication failed: Forbidden (status code: 403)")
            return {
                'success': False,
                'message': 'Authentication failed: Access forbidden',
                'details': {
                    'status_code': 403,
                    'error': 'Forbidden'
                }
            }
        else:
            logger.warning(f"API request returned unexpected status code: {response.status_code}")
            return {
                'success': False,
                'message': f'API request failed with status code {response.status_code}',
                'details': {
                    'status_code': response.status_code,
                    'response_json': response_json if isinstance(response_json, dict) else {},
                    'response_text': response.text[:1000] if response.text else ''
                }
            }

    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return {
            'success': False,
            'message': f'Connection error: {str(e)}',
            'details': {'url': base_url}
        }
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timeout: {str(e)}")
        return {
            'success': False,
            'message': f'Request timed out: {str(e)}',
            'details': {'url': base_url, 'timeout': 30}
        }
    except Exception as e:
        logger.exception(f"Unexpected error validating API: {str(e)}")
        return {
            'success': False,
            'message': f'Unexpected error: {str(e)}',
            'details': {'url': base_url}
        }

def validate_api_authentication(api_client):
    """
    Validate API authentication by making a simple test request.
    
    Args:
        api_client: Initialized API client
        
    Returns:
        bool: True if authentication is successful, False otherwise
    """
    try:
        logger.info("Testing API client authentication")
        
        # Make a simple GET request to test the connection
        # Using an empty endpoint which will just hit the base URL
        response_json, status_code = api_client.get('')
        
        # Check if the status code indicates successful authentication
        if status_code in (200, 201, 202, 204):
            logger.info(f"API client authentication successful with status code: {status_code}")
            return True
        elif status_code in (401, 403):
            logger.warning(f"API client authentication failed: Unauthorized (status code: {status_code})")
            return False
        else:
            logger.warning(f"API client authentication check returned unexpected status code: {status_code}")
            return False
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return False
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timeout: {str(e)}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Request exception: {str(e)}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error validating API client: {str(e)}")
        return False

def validate_excel_data(excel_path, sheet_name, required_columns=None):
    """
    Validate that an Excel file exists and contains the required sheet and columns.
    
    Args:
        excel_path: Path to Excel file
        sheet_name: Name of sheet to validate
        required_columns: List of required column names
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    logger.info(f"Validating Excel sheet: {sheet_name} in {excel_path}")
    
    try:
        # Check if file exists
        if not os.path.exists(excel_path):
            logger.error(f"Excel file not found: {excel_path}")
            return False
        
        # Check if file is readable
        try:
            with open(excel_path, 'rb') as f:
                pass
        except Exception as e:
            logger.error(f"Cannot read Excel file: {str(e)}")
            return False
        
        # Load the Excel file
        try:
            import pandas as pd
            xls = pd.ExcelFile(excel_path)
            
            # Get all sheet names (for better error messages)
            all_sheets = xls.sheet_names
            logger.info(f"Available sheets: {all_sheets}")
            
            # Check if the required sheet exists (case-sensitive)
            if sheet_name not in all_sheets:
                # Try case-insensitive match (for better error messages)
                sheet_lower = sheet_name.lower()
                matches = [s for s in all_sheets if s.lower() == sheet_lower]
                
                if matches:
                    logger.error(f"Sheet '{sheet_name}' not found, but found similar sheet: '{matches[0]}' (case sensitivity issue)")
                else:
                    logger.error(f"Sheet '{sheet_name}' not found in Excel file. Available sheets: {all_sheets}")
                return False
            
            # If we need to validate columns, read the sheet and check columns
            if required_columns:
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
                columns = df.columns.tolist()
                
                for col in required_columns:
                    if col not in columns:
                        logger.error(f"Required column '{col}' not found in sheet '{sheet_name}'")
                        return False
            
            # All validation passed
            logger.info(f"Excel validation passed for sheet: {sheet_name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error validating Excel file: {str(e)}")
            return False
            
    except Exception as e:
        logger.exception(f"Unexpected error in validate_excel_data: {str(e)}")
        return False
        
        # Set up module logger
logger = logging.getLogger(__name__)

def validate_required_spreadsheet(excel_path: str) -> Dict[str, Any]:
    """
    Comprehensive validation of the required spreadsheet.
    
    Args:
        excel_path (str): Path to the Excel file
    
    Returns:
        Dict containing validation results for required sheets
    """
    # Required sheets and their required column prefixes
    required_sheets = {
        'Compensation Plans': ['Plan Name', 'Plan Code', 'Plan Type'],
        'Plan Components': ['Plan Component Name', 'Plan Component Code', 'Plan Name'],
        'Rate Table': ['Rate Table Name', 'Rate Table Code', 'Rate Table Type'],
        'Rate Dimension': ['Rate Dimension Name', 'Rate Dimension Code', 'Sequence'],
        'Expression': ['Expression Name', 'Expression Code', 'Description'],
        'Performance Measure': ['Measure Name', 'Measure Code', 'Credit Category'],
        'Rate Table Rates': ['Rate Table Name', 'Rate Dimension', 'Rate']
    }
    
    # Validation results dictionary
    validation_results = {
        'success': True,
        'details': {}
    }
    
    # Check if file exists
    if not os.path.exists(excel_path):
        return {
            'success': False,
            'message': f'Excel file not found: {excel_path}',
            'details': {}
        }
    
    try:
        # Read Excel file
        xls = pd.ExcelFile(excel_path)
        available_sheets = xls.sheet_names
        
        # Validate each required sheet
        for sheet, required_columns in required_sheets.items():
            sheet_validation = {'success': False, 'errors': []}
            
            # Check sheet existence (case-sensitive and case-insensitive)
            if sheet not in available_sheets:
                # Try case-insensitive match
                case_insensitive_match = [s for s in available_sheets if s.lower() == sheet.lower()]
                
                if case_insensitive_match:
                    sheet_validation['errors'].append(f"Sheet '{sheet}' found with different capitalization")
                else:
                    sheet_validation['errors'].append(f"Sheet '{sheet}' not found")
                
                validation_results['details'][sheet] = sheet_validation
                validation_results['success'] = False
                continue
            
            # Read sheet
            try:
                df = pd.read_excel(excel_path, sheet_name=sheet)
                columns = df.columns.tolist()
                
                # Check for required columns
                missing_columns = []
                for col_prefix in required_columns:
                    matching_columns = [col for col in columns if col.startswith(col_prefix)]
                    if not matching_columns:
                        missing_columns.append(col_prefix)
                
                # Update sheet validation
                if missing_columns:
                    sheet_validation['success'] = False
                    sheet_validation['errors'].append(f"Missing columns with prefixes: {', '.join(missing_columns)}")
                else:
                    sheet_validation['success'] = True
                
                # Add additional details
                sheet_validation['total_rows'] = len(df)
                sheet_validation['columns'] = columns
                
                validation_results['details'][sheet] = sheet_validation
                
                # Update overall validation success
                if not sheet_validation['success']:
                    validation_results['success'] = False
                
            except Exception as sheet_error:
                sheet_validation['success'] = False
                sheet_validation['errors'].append(f"Error reading sheet: {str(sheet_error)}")
                validation_results['details'][sheet] = sheet_validation
                validation_results['success'] = False
        
        # Add list of available sheets to results
        validation_results['available_sheets'] = available_sheets
        
        return validation_results
    
    except Exception as e:
        logger.error(f"Unexpected error validating spreadsheet: {str(e)}")
        return {
            'success': False,
            'message': f'Unexpected error: {str(e)}',
            'details': {}
        }