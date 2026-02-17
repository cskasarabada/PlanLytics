"""
API Client for interacting with Oracle ICM REST API.
Handles authentication and HTTP requests.
"""

import requests
import logging
from typing import Tuple, Any

class APIClient:
    def __init__(self, base_url: str, username: str, password: str):
        # Sanitize base_url to ensure it ends with the domain, removing only the API path if present at the end
        self.base_url = base_url.rstrip('/')
        if self.base_url.endswith('/fscmRestApi/resources/11.13.18.05'):
            self.base_url = self.base_url[:-(len('/fscmRestApi/resources/11.13.18.05'))].rstrip('/')
        self.api_path = '/fscmRestApi/resources/11.13.18.05'  # Fixed API path
        self.username = username
        self.password = password
        self.logger = logging.getLogger(__name__)
        self.logger.debug(f"Initialized APIClient with base_url: {self.base_url}, api_path: {self.api_path}")

    def _build_url(self, endpoint: str) -> str:
        """Build the full URL by appending the endpoint to the base URL and API path, avoiding duplication."""
        # Ensure endpoint is a relative path
        if endpoint.startswith('/'):
            endpoint = endpoint[1:]
        # Construct the full URL, checking for API path duplication
        full_url = self.base_url
        if not full_url.endswith(self.api_path):
            full_url += self.api_path
        full_url += f"/{endpoint}"
        self.logger.debug(f"Built URL: {full_url}")
        return full_url

    def get(self, endpoint: str) -> Tuple[Any, int]:
        """Perform a GET request to the specified endpoint."""
        url = self._build_url(endpoint)
        self.logger.debug(f"GET request to: {url}")
        try:
            response = requests.get(url, auth=(self.username, self.password), timeout=30)
            response.raise_for_status()
            self.logger.debug(f"GET response status: {response.status_code}")
            try:
                return response.json(), response.status_code
            except ValueError:
                self.logger.warning(f"Response is not JSON: {response.text}")
                return response.text, response.status_code
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request Error in GET request to {url}: {str(e)}")
            self.logger.error(f"{e.response.status_code if e.response else 'No response'} Error Details: {e.response.text if e.response else ''}")
            return None, e.response.status_code if e.response else 400

    def post(self, endpoint: str, data: dict) -> Tuple[Any, int]:
        """Perform a POST request to the specified endpoint with data."""
        url = self._build_url(endpoint)
        self.logger.debug(f"POST request to: {url}")
        self.logger.debug(f"Payload: {data}")
        try:
            response = requests.post(url, json=data, auth=(self.username, self.password), timeout=30)
            response.raise_for_status()
            self.logger.debug(f"POST response status: {response.status_code}")
            try:
                return response.json(), response.status_code
            except ValueError:
                self.logger.warning(f"Response is not JSON: {response.text}")
                return response.text, response.status_code
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request Error in POST request to {url}: {str(e)}")
            self.logger.error(f"{e.response.status_code if e.response else 'No response'} Error Details: {e.response.text if e.response else ''}")
            self.logger.error(f"Payload: {data}")
            return None, e.response.status_code if e.response else 400

    def patch(self, endpoint: str, data: dict) -> Tuple[Any, int]:
        """Perform a PATCH request to the specified endpoint with data."""
        url = self._build_url(endpoint)
        self.logger.debug(f"PATCH request to: {url}")
        self.logger.debug(f"Payload: {data}")
        try:
            response = requests.patch(url, json=data, auth=(self.username, self.password), timeout=30)
            response.raise_for_status()
            self.logger.debug(f"PATCH response status: {response.status_code}")
            try:
                return response.json(), response.status_code
            except ValueError:
                self.logger.warning(f"Response is not JSON: {response.text}")
                return response.text, response.status_code
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request Error in PATCH request to {url}: {str(e)}")
            self.logger.error(f"{e.response.status_code if e.response else 'No response'} Error Details: {e.response.text if e.response else ''}")
            self.logger.error(f"Payload: {data}")
            return None, e.response.status_code if e.response else 400

    def create_api_client_from_config(config):
        """
        Create an APIClient instance from a configuration.

        Args:
            config: Configuration object with API settings

        Returns:
            APIClient instance
        """
        api_config = config.get_section('api')
        if not all(key in api_config for key in ['base_url', 'username', 'password']):
            raise ValueError("API config missing required keys: base_url, username, password")
        return APIClient(
            base_url=api_config['base_url'],
            username=api_config['username'],
            password=api_config['password']
        )