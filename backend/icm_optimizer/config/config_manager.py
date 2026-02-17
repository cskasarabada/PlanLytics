"""
Configuration Manager for ICM Optimizer
Location: app/config/config_manager.py
"""

import os
import yaml
import logging
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self, config_path: str):
        """
        Initialize ConfigManager with the path to the configuration file.
        
        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = config_path
        self.config = {}
        self.logger = logging.getLogger(__name__)
        
        # Load configuration on initialization
        self._load_config()
    
    def _load_config(self) -> None:
        """
        Load configuration from YAML file.
        """
        try:
            self.logger.info(f"Loading configuration from: {self.config_path}")
            
            # Check if file exists
            if not os.path.exists(self.config_path):
                self.logger.error(f"Configuration file not found: {self.config_path}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            # Load YAML file
            with open(self.config_path, 'r') as config_file:
                self.config = yaml.safe_load(config_file)
            
            # Log loaded sections
            if self.config:
                section_keys = list(self.config.keys())
                self.logger.info(f"Configuration loaded successfully with sections: {section_keys}")
            else:
                self.logger.warning("Configuration file is empty")
                
        except Exception as e:
            self.logger.exception(f"Error loading configuration: {str(e)}")
            raise
    
    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        """
        Get configuration value by section and key.
        
        Args:
            section: Configuration section
            key: Configuration key (optional)
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        try:
            # If no key is provided, return the entire section
            if key is None:
                return self.config.get(section, default)
                
            # Otherwise, return the specific key from the section
            return self.config.get(section, {}).get(key, default)
            
        except (AttributeError, KeyError):
            self.logger.warning(f"Configuration value not found for [{section}]{'.'+key if key else ''}")
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Configuration section
            
        Returns:
            Dictionary containing section data or empty dict if not found
        """
        return self.config.get(section, {})
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get entire configuration.
        
        Returns:
            Dictionary containing all configuration data
        """
        return self.config
    
    def set(self, section: str, key: str, value: Any) -> None:
        """
        Set configuration value by section and key.
        
        Args:
            section: Configuration section
            key: Configuration key
            value: Value to set
        """
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = value
    
    def save(self, output_path: Optional[str] = None) -> None:
        """
        Save configuration to YAML file.
        
        Args:
            output_path: Path to save configuration (uses current config path by default)
        """
        save_path = output_path or self.config_path
        
        try:
            self.logger.info(f"Saving configuration to: {save_path}")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save configuration
            with open(save_path, 'w') as config_file:
                yaml.dump(self.config, config_file, default_flow_style=False)
                
            self.logger.info("Configuration saved successfully")
            
        except Exception as e:
            self.logger.exception(f"Error saving configuration: {str(e)}")
            raise