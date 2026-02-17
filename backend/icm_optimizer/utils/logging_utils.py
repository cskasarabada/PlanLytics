"""
Comprehensive Logging Utility for ICM Optimizer
Location: app/utils/logging_utils.py
"""

import os
import csv
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add the missing functions and classes that are imported in __init__.py

def setup_logging(log_level: str = 'INFO', log_file: Optional[str] = None):
    """
    Setup application logging with the specified configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs to console only.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Basic configuration
    logging_config = {
        'level': numeric_level,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'datefmt': '%Y-%m-%d %H:%M:%S',
    }
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        logging_config['filename'] = log_file
        logging_config['filemode'] = 'a'
    
    logging.basicConfig(**logging_config)
    
    return logging.getLogger(__name__)

def log_api_response(message: str, data: Dict[str, Any] = None, log_file: Optional[str] = None):
    """
    Log API response details at appropriate log levels based on a message and data dictionary.
    
    Args:
        message: Descriptive message for the log entry
        data: Dictionary containing status_code, response, and other details
        log_file: Optional path to additional log file
    """
    logger = logging.getLogger(__name__)
    log_data = {
        'message': message,
        'status_code': data.get("status_code") if data else None,
        'response': data.get("response") if data else None,
        'timestamp': datetime.now().isoformat()
    }

    # Determine log level based on status code
    status_code = data.get("status_code") if data else None
    if status_code is not None:
        if 200 <= status_code < 300:
            logger.info(json.dumps(log_data))
        elif 400 <= status_code < 500:
            logger.warning(json.dumps(log_data))
        elif 500 <= status_code < 600:
            logger.error(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))
    else:
        logger.info(json.dumps(log_data))

    # Log to file if specified
    if log_file:
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except IOError as e:
            logger.error(f"Failed to write to log file {log_file}: {e}")

class CorrelationFilter(logging.Filter):
    """
    Filter that adds correlation ID to log records for request tracing
    """
    def __init__(self, correlation_id=None):
        super().__init__()
        self.correlation_id = correlation_id or datetime.now().strftime("%Y%m%d%H%M%S%f")
        
    def filter(self, record):
        record.correlation_id = self.correlation_id
        return True

class JsonFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging
    """
    def format(self, record):
        log_record = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        # Add correlation ID if available
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
            
        return json.dumps(log_record)

class LoggerAdapter(logging.LoggerAdapter):
    """
    Adapter that adds context to log messages
    """
    def __init__(self, logger, extra=None):
        super().__init__(logger, extra or {})
    
    def process(self, msg, kwargs):
        context_str = ' '.join(f'{k}={v}' for k, v in self.extra.items())
        return f"{msg} [{context_str}]", kwargs

class OptimizationLogger:
    def __init__(self, log_dir: str = 'logs'):
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_filename = os.path.join(log_dir, f'icm_optimizer_log_{timestamp}')
        
        self.log_data = {
            'start_time': datetime.now().isoformat(),
            'steps': [],
            'overall_status': 'Pending',
            'total_steps': 0,
            'successful_steps': 0,
            'failed_steps': 0
        }
        
        self.logger = logging.getLogger(__name__)
    
    def log_step_start(self, step_name: str):
        step_log = {
            'name': step_name,
            'start_time': datetime.now().isoformat(),
            'status': 'Running',
            'details': {},
            'objects_created': [],
            'warnings': [],
            'errors': []
        }
        self.log_data['steps'].append(step_log)
        self.log_data['total_steps'] += 1
    
    def log_step_success(self, objects_created: List[str] = None, details: Dict[str, Any] = None):
        current_step = self.log_data['steps'][-1]
        current_step.update({
            'status': 'Success',
            'end_time': datetime.now().isoformat(),
            'objects_created': objects_created or [],
            'details': details or {}
        })
        self.log_data['successful_steps'] += 1
    
    def log_step_failure(self, error_message: str, exception: Exception = None):
        current_step = self.log_data['steps'][-1]
        current_step.update({
            'status': 'Failed',
            'end_time': datetime.now().isoformat(),
            'errors': [
                {
                    'message': error_message,
                    'exception_type': str(type(exception).__name__) if exception else None,
                    'exception_details': str(exception) if exception else None
                }
            ]
        })
        self.log_data['failed_steps'] += 1
    
    def finalize(self) -> Dict[str, str]:
        if self.log_data['failed_steps'] > 0:
            self.log_data['overall_status'] = 'Partial Failure'
        elif self.log_data['successful_steps'] == self.log_data['total_steps']:
            self.log_data['overall_status'] = 'Success'
        
        self.log_data['end_time'] = datetime.now().isoformat()
        
        log_files = {
            'json': f'{self.base_filename}.json',
            'csv': f'{self.base_filename}.csv'
        }
        
        # Write JSON log
        with open(log_files['json'], 'w') as f:
            json.dump(self.log_data, f, indent=2)
        
        # Write CSV log
        self._write_csv_log(log_files['csv'])
        
        return log_files
    
    def _write_csv_log(self, csv_path: str):
        with open(csv_path, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            
            # Write headers
            csv_writer.writerow([
                'Step Name', 'Status', 'Start Time', 'End Time', 
                'Objects Created', 'Warnings', 'Errors'
            ])
            
            # Write step details
            for step in self.log_data['steps']:
                row = [
                    step.get('name', ''),
                    step.get('status', ''),
                    step.get('start_time', ''),
                    step.get('end_time', ''),
                    ', '.join(map(str, step.get('objects_created', []))),
                    ', '.join(step.get('warnings', [])),
                    ', '.join([
                        f"{err.get('message', '')} ({err.get('exception_type', '')})" 
                        for err in step.get('errors', [])
                    ])
                ]
                csv_writer.writerow(row)
            
            # Write summary
            csv_writer.writerow([])
            csv_writer.writerow(['Overall Summary'])
            csv_writer.writerow(['Total Steps', self.log_data['total_steps']])
            csv_writer.writerow(['Successful Steps', self.log_data['successful_steps']])
            csv_writer.writerow(['Failed Steps', self.log_data['failed_steps']])
            csv_writer.writerow(['Overall Status', self.log_data['overall_status']])