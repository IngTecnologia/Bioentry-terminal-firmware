"""
Comprehensive API Client for BioEntry Terminal
Handles all communication with the FastAPI backend server.

IMPORTANT: This module provides the complete integration with the BioEntry API.
All endpoints and data formats are based on the actual API implementation.
"""

import requests
import json
import os
import time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import uuid
from pathlib import Path
import asyncio
import threading
from dataclasses import dataclass, asdict

from utils.config import get_config
from utils.logger import get_logger


@dataclass
class APIResponse:
    """Standard API response structure"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class VerificationResult:
    """Facial verification result from API"""
    verified: bool
    distance: float
    cedula: str
    nombre: str
    tipo_registro: str
    record_id: str
    timestamp: str
    ubicacion: str
    mensaje: str
    fuera_de_ubicacion: bool = False
    distancia_ubicacion: int = 0


@dataclass
class BulkRecord:
    """Record structure for bulk sync"""
    user_id: Optional[int]
    cedula: str
    employee_name: str
    access_timestamp: str
    method: str  # 'online' | 'offline'
    verification_type: str  # 'facial' | 'fingerprint' | 'manual'
    confidence_score: Optional[float]
    device_id: str
    location_name: Optional[str]
    terminal_record_id: str
    created_at: str


@dataclass
class TerminalConfig:
    """Terminal configuration from API"""
    terminal_id: str
    location: Dict[str, Any]
    hardware: Dict[str, bool]
    operation: Dict[str, Any]
    display: Dict[str, Any]
    sync: Dict[str, Any]


class APIClient:
    """
    Complete API client for BioEntry terminal communication.
    
    This class handles all API interactions including:
    - Health checks and connectivity monitoring
    - Facial verification (both manual and automatic)
    - Data synchronization (users and records)
    - Terminal configuration retrieval
    - Bulk record uploads
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # API Configuration
        self.base_url = self.config.api.base_url
        self.terminal_id = self.config.api.terminal_id
        self.api_key = self.config.api.api_key
        self.timeout = self.config.api.timeout
        
        # Request headers
        self.headers = {
            'X-API-Key': self.api_key,
            'Accept': 'application/json'
        }
        
        # Connection state
        self.is_online = False
        self.last_health_check = None
        self.health_check_interval = 30  # seconds
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        
        self.logger.info(f"API Client initialized for terminal {self.terminal_id}")
    
    # ==========================================
    # CONNECTIVITY AND HEALTH CHECKS
    # ==========================================
    
    async def check_connectivity(self) -> bool:
        """
        Quick connectivity check to determine online/offline status.
        Uses the /terminal-health endpoint for fast response.
        """
        try:
            response = await self._make_request(
                'GET',
                f'/terminal-health/{self.terminal_id}',
                timeout=5  # Quick timeout for health checks
            )
            
            if response.success:
                self.is_online = True
                self.last_health_check = datetime.now()
                return True
            else:
                self.is_online = False
                return False
                
        except Exception as e:
            self.logger.warning(f"Connectivity check failed: {str(e)}")
            self.is_online = False
            return False
    
    async def get_health_status(self) -> APIResponse:
        """
        Get detailed health status from the API.
        Returns server status and service availability.
        """
        return await self._make_request(
            'GET',
            f'/terminal-health/{self.terminal_id}'
        )
    
    async def get_terminal_config(self) -> APIResponse:
        """
        Retrieve terminal-specific configuration from the API.
        Includes location, hardware settings, and operational parameters.
        """
        return await self._make_request(
            'GET',
            f'/terminal-config/{self.terminal_id}'
        )
    
    # ==========================================
    # FACIAL VERIFICATION
    # ==========================================
    
    async def verify_face_manual(self, cedula: str, image_bytes: bytes, 
                               tipo_registro: str, lat: Optional[float] = None, 
                               lng: Optional[float] = None) -> APIResponse:
        """
        Manual facial verification with known cedula.
        
        Args:
            cedula: User's document ID
            image_bytes: Facial image as bytes
            tipo_registro: 'entrada' or 'salida'
            lat: Optional latitude
            lng: Optional longitude
        
        Returns:
            APIResponse with verification result
        """
        files = {
            'image': ('capture.jpg', image_bytes, 'image/jpeg')
        }
        
        data = {
            'cedula': cedula,
            'terminal_id': self.terminal_id,
            'tipo_registro': tipo_registro
        }
        
        if lat is not None and lng is not None:
            data['lat'] = lat
            data['lng'] = lng
        
        return await self._make_request(
            'POST',
            '/verify-terminal',
            files=files,
            data=data
        )
    
    async def verify_face_automatic(self, image_bytes: bytes, 
                                  lat: Optional[float] = None, 
                                  lng: Optional[float] = None) -> APIResponse:
        """
        Automatic facial verification - identifies user and detects entry/exit type.
        This is the primary method for terminal operation.
        
        Args:
            image_bytes: Facial image as bytes
            lat: Optional latitude
            lng: Optional longitude
        
        Returns:
            APIResponse with complete verification result including user identification
        """
        files = {
            'image': ('capture.jpg', image_bytes, 'image/jpeg')
        }
        
        data = {
            'terminal_id': self.terminal_id
        }
        
        if lat is not None and lng is not None:
            data['lat'] = lat
            data['lng'] = lng
        
        return await self._make_request(
            'POST',
            '/verify-terminal/auto',
            files=files,
            data=data
        )
    
    # ==========================================
    # DATA SYNCHRONIZATION
    # ==========================================
    
    async def sync_user_database(self, last_sync: Optional[str] = None) -> APIResponse:
        """
        Synchronize user database from server.
        Downloads optimized user data for local storage.
        
        Args:
            last_sync: ISO timestamp of last synchronization
        
        Returns:
            APIResponse with user database records
        """
        params = {}
        if last_sync:
            params['last_sync'] = last_sync
        
        return await self._make_request(
            'GET',
            f'/terminal-sync/{self.terminal_id}',
            params=params
        )
    
    async def check_sync_status(self) -> APIResponse:
        """
        Check if database synchronization is needed.
        Fast endpoint to determine if local data is up to date.
        """
        return await self._make_request(
            'GET',
            f'/terminal-sync/{self.terminal_id}/check'
        )
    
    async def upload_bulk_records(self, records: List[BulkRecord]) -> APIResponse:
        """
        Upload multiple access records in batch.
        Used for synchronizing offline records with the server.
        
        Args:
            records: List of BulkRecord objects to upload
        
        Returns:
            APIResponse with upload results and status per record
        """
        if not records:
            return APIResponse(success=False, error="No records to upload")
        
        # Convert records to API format
        bulk_data = {
            'terminal_id': self.terminal_id,
            'records': [asdict(record) for record in records],
            'sync_timestamp': datetime.utcnow().isoformat()
        }
        
        return await self._make_request(
            'POST',
            '/terminal-records/bulk',
            json_data=bulk_data
        )
    
    async def get_records_status(self) -> APIResponse:
        """
        Get statistics about records for this terminal.
        Useful for monitoring and debugging.
        """
        return await self._make_request(
            'GET',
            f'/terminal-records/status/{self.terminal_id}'
        )
    
    # ==========================================
    # UTILITY METHODS
    # ==========================================
    
    async def _make_request(self, method: str, endpoint: str, 
                          files: Optional[Dict] = None,
                          data: Optional[Dict] = None,
                          json_data: Optional[Dict] = None,
                          params: Optional[Dict] = None,
                          timeout: Optional[int] = None) -> APIResponse:
        """
        Make HTTP request to API with retry logic and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            files: Files to upload
            data: Form data
            json_data: JSON payload
            params: Query parameters
            timeout: Request timeout
        
        Returns:
            APIResponse object with result
        """
        url = f"{self.base_url}{endpoint}"
        timeout = timeout or self.timeout
        
        for attempt in range(self.max_retries + 1):
            try:
                # Prepare request arguments
                kwargs = {
                    'headers': self.headers.copy(),
                    'timeout': timeout
                }
                
                if files:
                    kwargs['files'] = files
                if data:
                    kwargs['data'] = data
                if json_data:
                    kwargs['json'] = json_data
                    kwargs['headers']['Content-Type'] = 'application/json'
                if params:
                    kwargs['params'] = params
                
                # Make the request
                if method.upper() == 'GET':
                    response = requests.get(url, **kwargs)
                elif method.upper() == 'POST':
                    response = requests.post(url, **kwargs)
                elif method.upper() == 'PUT':
                    response = requests.put(url, **kwargs)
                elif method.upper() == 'DELETE':
                    response = requests.delete(url, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                # Handle response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return APIResponse(success=True, data=data, status_code=response.status_code)
                    except json.JSONDecodeError:
                        return APIResponse(success=True, data={'raw': response.text}, status_code=response.status_code)
                
                elif response.status_code in [400, 403, 404]:
                    # Client errors - don't retry
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('detail', f'HTTP {response.status_code}')
                    except:
                        error_msg = f'HTTP {response.status_code}: {response.text}'
                    
                    return APIResponse(success=False, error=error_msg, status_code=response.status_code)
                
                else:
                    # Server errors - retry
                    if attempt < self.max_retries:
                        self.logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): HTTP {response.status_code}")
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        return APIResponse(success=False, error=f'HTTP {response.status_code}', status_code=response.status_code)
            
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    self.logger.warning(f"Request timeout (attempt {attempt + 1}/{self.max_retries + 1})")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return APIResponse(success=False, error="Request timeout")
            
            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries:
                    self.logger.warning(f"Connection error (attempt {attempt + 1}/{self.max_retries + 1})")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return APIResponse(success=False, error="Connection error")
            
            except Exception as e:
                if attempt < self.max_retries:
                    self.logger.warning(f"Unexpected error (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}")
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    return APIResponse(success=False, error=f"Unexpected error: {str(e)}")
        
        return APIResponse(success=False, error="Max retries exceeded")
    
    def parse_verification_result(self, api_response: APIResponse) -> Optional[VerificationResult]:
        """
        Parse API response into VerificationResult object.
        
        Args:
            api_response: Response from verify_face_automatic or verify_face_manual
        
        Returns:
            VerificationResult object or None if parsing fails
        """
        if not api_response.success or not api_response.data:
            return None
        
        try:
            data = api_response.data
            return VerificationResult(
                verified=data.get('verified', False),
                distance=data.get('distance', 1.0),
                cedula=data.get('cedula', ''),
                nombre=data.get('nombre', 'Usuario'),
                tipo_registro=data.get('tipo_registro', 'entrada'),
                record_id=data.get('record_id', ''),
                timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
                ubicacion=data.get('ubicacion', 'Terminal'),
                mensaje=data.get('mensaje', 'Verificación completada'),
                fuera_de_ubicacion=data.get('fuera_de_ubicacion', False),
                distancia_ubicacion=data.get('distancia_ubicacion', 0)
            )
        except Exception as e:
            self.logger.error(f"Error parsing verification result: {str(e)}")
            return None
    
    def parse_terminal_config(self, api_response: APIResponse) -> Optional[TerminalConfig]:
        """
        Parse API response into TerminalConfig object.
        
        Args:
            api_response: Response from get_terminal_config
        
        Returns:
            TerminalConfig object or None if parsing fails
        """
        if not api_response.success or not api_response.data:
            return None
        
        try:
            config_data = api_response.data.get('config', {})
            return TerminalConfig(
                terminal_id=config_data.get('terminal_id', self.terminal_id),
                location=config_data.get('location', {}),
                hardware=config_data.get('hardware', {}),
                operation=config_data.get('operation', {}),
                display=config_data.get('display', {}),
                sync=config_data.get('sync', {})
            )
        except Exception as e:
            self.logger.error(f"Error parsing terminal config: {str(e)}")
            return None
    
    # ==========================================
    # BACKGROUND TASKS
    # ==========================================
    
    async def start_health_monitor(self, callback: Optional[callable] = None):
        """
        Start background health monitoring.
        
        Args:
            callback: Optional function to call on connectivity change
        """
        while True:
            try:
                previous_status = self.is_online
                current_status = await self.check_connectivity()
                
                if previous_status != current_status:
                    self.logger.info(f"Connectivity status changed: {current_status}")
                    if callback:
                        callback(current_status)
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                self.logger.error(f"Health monitor error: {str(e)}")
                await asyncio.sleep(self.health_check_interval)


# Global API client instance
_api_client = None


def get_api_client() -> APIClient:
    """Get the global API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client


if __name__ == "__main__":
    # Test the API client
    import asyncio
    
    async def test_api_client():
        client = get_api_client()
        
        # Test health check
        print("Testing connectivity...")
        health = await client.get_health_status()
        print(f"Health check: {health}")
        
        # Test config retrieval
        print("Testing config retrieval...")
        config = await client.get_terminal_config()
        print(f"Config: {config}")
        
        # Test sync status
        print("Testing sync status...")
        sync_status = await client.check_sync_status()
        print(f"Sync status: {sync_status}")
    
    asyncio.run(test_api_client())