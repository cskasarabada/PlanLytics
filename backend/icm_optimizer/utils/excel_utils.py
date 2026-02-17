import os
import pandas as pd
import logging
import glob
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_excel_file(directory, pattern="*.xlsx"):
    """
    Find an Excel file in the specified directory matching the given pattern.
    
    Args:
        directory (str): Directory to search in
        pattern (str): Glob pattern to match files (default: "*.xlsx")
        
    Returns:
        str: Path to the found Excel file, or None if not found
    """
    logger.info(f"Searching for Excel files in {directory} with pattern {pattern}")
    
    # Ensure the directory exists
    if not os.path.exists(directory):
        logger.error(f"Directory {directory} does not exist")
        return None
    
    # Search for Excel files
    excel_files = glob.glob(os.path.join(directory, pattern))
    
    if not excel_files:
        logger.warning(f"No Excel files found in {directory} with pattern {pattern}")
        return None
    
    # If multiple files found, use the first one
    if len(excel_files) > 1:
        logger.warning(f"Multiple Excel files found, using {excel_files[0]}")
    
    logger.info(f"Found Excel file: {excel_files[0]}")
    return excel_files[0]

def load_excel_data(file_path, sheet_name=None):
    """
    Load data from an Excel file.
    
    Args:
        file_path (str): Path to the Excel file
        sheet_name (str, optional): Name of the sheet to load. If None, loads all sheets.
        
    Returns:
        dict or DataFrame: Dictionary mapping sheet names to DataFrames if sheet_name is None,
                          otherwise a single DataFrame for the specified sheet
    """
    logger.info(f"Loading data from Excel file: {file_path}")
    
    try:
        if sheet_name:
            logger.info(f"Loading sheet: {sheet_name}")
            return pd.read_excel(file_path, sheet_name=sheet_name)
        else:
            logger.info("Loading all sheets")
            return pd.read_excel(file_path, sheet_name=None)
    except Exception as e:
        logger.error(f"Error loading Excel data: {str(e)}")
        raise

def save_excel_data(data, file_path, sheet_name="Sheet1", index=False):
    """
    Save data to an Excel file.
    
    Args:
        data (DataFrame): Data to save
        file_path (str): Path to save the Excel file
        sheet_name (str): Name of the sheet
        index (bool): Whether to write row names (index)
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Saving data to Excel file: {file_path}, sheet: {sheet_name}")
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save data
        data.to_excel(file_path, sheet_name=sheet_name, index=index)
        logger.info(f"Data successfully saved to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving Excel data: {str(e)}")
        return False

def get_sheet_names(file_path):
    """
    Get the names of all sheets in an Excel file.
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        list: List of sheet names
    """
    try:
        logger.info(f"Getting sheet names from {file_path}")
        xlsx = pd.ExcelFile(file_path)
        sheet_names = xlsx.sheet_names
        logger.info(f"Found sheets: {sheet_names}")
        return sheet_names
    except Exception as e:
        logger.error(f"Error getting sheet names from {file_path}: {str(e)}")
        return []

def find_excel_file(directory_list, pattern="*.xlsx", sheet_name=None, required_columns=None):
    """
    Find an Excel file in the specified directories matching the given pattern
    or use a direct file path, and optionally validate it contains a specific sheet
    with required columns.
    
    Args:
        directory_list (str or list): Directory, list of directories, or direct file path(s)
        pattern (str): Glob pattern to match files (default: "*.xlsx")
        sheet_name (str, optional): Name of sheet that must exist in the file
        required_columns (list, optional): List of column names that must exist in the sheet
        
    Returns:
        str: Path to the found Excel file, or None if not found or validation fails
    """
    logger.info(f"Searching for Excel file(s) in: {directory_list}")
    
    # Handle single directory/file as string
    if isinstance(directory_list, str):
        directory_list = [directory_list]
    
    # Process each path
    for path in directory_list:
        # Check if path is a direct file path (not a directory)
        if os.path.isfile(path):
            logger.info(f"Found direct file path: {path}")
            file_path = path
            
            # Validate sheet existence if requested
            if sheet_name:
                sheet_names = get_sheet_names(file_path)
                if sheet_name not in sheet_names:
                    logger.warning(f"Sheet '{sheet_name}' not found in {file_path}")
                    continue
                
                # Validate required columns if requested
                if required_columns:
                    try:
                        df = load_excel_data(file_path, sheet_name)
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        if missing_columns:
                            logger.warning(f"Missing required columns {missing_columns} in {file_path}, sheet {sheet_name}")
                            continue
                    except Exception as e:
                        logger.warning(f"Error loading sheet {sheet_name} from {file_path}: {str(e)}")
                        continue
                    
                    logger.info(f"Validated {file_path} contains sheet '{sheet_name}' with required columns")
            
            return file_path
            
        # Handle directory path
        elif os.path.isdir(path):
            # Search for Excel files
            excel_files = glob.glob(os.path.join(path, pattern))
            
            if not excel_files:
                logger.warning(f"No Excel files found in {path} with pattern {pattern}")
                continue
            
            # If multiple files found, use the first one
            if len(excel_files) > 1:
                logger.warning(f"Multiple Excel files found in {path}, using {excel_files[0]}")
            
            file_path = excel_files[0]
            logger.info(f"Found Excel file: {file_path}")
            
            # Validate sheet existence if requested
            if sheet_name:
                sheet_names = get_sheet_names(file_path)
                if sheet_name not in sheet_names:
                    logger.warning(f"Sheet '{sheet_name}' not found in {file_path}")
                    continue
                
                # Validate required columns if requested
                if required_columns:
                    try:
                        df = load_excel_data(file_path, sheet_name)
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        if missing_columns:
                            logger.warning(f"Missing required columns {missing_columns} in {file_path}, sheet {sheet_name}")
                            continue
                    except Exception as e:
                        logger.warning(f"Error loading sheet {sheet_name} from {file_path}: {str(e)}")
                        continue
                    
                    logger.info(f"Validated {file_path} contains sheet '{sheet_name}' with required columns")
            
            return file_path
        else:
            logger.warning(f"Path does not exist: {path}")
    
    logger.error(f"No valid Excel file found in {directory_list} with pattern {pattern}")
    return None

def process_compensation_plans(excel_file):
    """
    Process compensation plans from an Excel file.
    
    Args:
        excel_file (str): Path to the Excel file containing compensation plans
        
    Returns:
        DataFrame: Processed compensation plans data
    """
    logger.info(f"Processing compensation plans from: {excel_file}")
    
    try:
        # Load the compensation plans sheet
        plans_df = load_excel_data(excel_file, "Compensation Plans")
        
        # Basic validation
        required_columns = ['Name', 'StartDate', 'EndDate', 'Status', 'TargetIncentive']
        for col in required_columns:
            if col not in plans_df.columns:
                logger.error(f"Required column '{col}' not found in compensation plans sheet")
                raise ValueError(f"Required column '{col}' not found in compensation plans sheet")
        
        # Convert date columns if they exist
        date_columns = ['StartDate', 'EndDate']
        for col in date_columns:
            if col in plans_df.columns and not pd.api.types.is_datetime64_any_dtype(plans_df[col]):
                plans_df[col] = pd.to_datetime(plans_df[col], errors='coerce')
        
        logger.info(f"Processed {len(plans_df)} compensation plans")
        return plans_df
    
    except Exception as e:
        logger.error(f"Error processing compensation plans: {str(e)}")
        raise	