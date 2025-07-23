"""
Fingerprint Manager for BioEntry Terminal
Handles AS608 fingerprint sensor operations and template management.
"""

import asyncio
import time
import random
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from utils.config import get_config
from utils.logger import get_logger


class FingerprintManager:
    """
    Fingerprint manager for AS608 sensor communication.
    
    Supports both real hardware (AS608 via UART) and mock mode for development.
    The AS608 sensor can store up to 162 fingerprint templates.
    """
    
    def __init__(self):
        self.config = get_config() 
        self.logger = get_logger()
        
        # Hardware configuration
        self.uart_port = self.config.hardware.fingerprint_uart_port
        self.baudrate = self.config.hardware.fingerprint_baudrate
        self.timeout = self.config.hardware.fingerprint_timeout
        
        # Sensor state
        self.sensor = None
        self.is_initialized = False
        self.template_count = 0
        self.max_templates = 162  # AS608 sensor capacity
        
        # Mock mode detection
        self.mock_mode = self.config.is_mock_mode() or not self.config.hardware.fingerprint_enabled
        
        # Mock data for development
        self.mock_templates = {}  # template_id -> mock fingerprint data
        self.mock_enrolled_users = {
            1: {'user_id': 1, 'cedula': '12345678', 'name': 'Usuario Test 1'},
            2: {'user_id': 2, 'cedula': '87654321', 'name': 'Usuario Test 2'},
            5: {'user_id': 5, 'cedula': '11111111', 'name': 'Administrador'}
        }
        
        self.logger.info(f"Fingerprint manager initialized - Mock mode: {self.mock_mode}")
    
    async def initialize(self) -> bool:
        """
        Initialize fingerprint sensor hardware or mock sensor.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if self.mock_mode:
                return await self._initialize_mock_sensor()
            else:
                return await self._initialize_real_sensor()
        except Exception as e:
            self.logger.error(f"Fingerprint sensor initialization failed: {str(e)}")
            return False
    
    async def _initialize_real_sensor(self) -> bool:
        """Initialize real AS608 fingerprint sensor."""
        try:
            # Try to import fingerprint sensor library
            from pyfingerprint import PyFingerprint
            
            # Initialize sensor
            self.sensor = PyFingerprint(self.uart_port, self.baudrate, 0xFFFFFFFF, 0x00000000)
            
            # Verify sensor connection
            if not self.sensor.verifyPassword():
                raise Exception("Sensor password verification failed")
            
            # Get template count
            self.template_count = self.sensor.getTemplateCount()
            
            self.is_initialized = True
            self.logger.info(f"AS608 sensor initialized: {self.template_count}/{self.max_templates} templates")
            return True
            
        except ImportError:
            self.logger.error("PyFingerprint library not available")
            return False
        except Exception as e:
            self.logger.error(f"Real sensor initialization failed: {str(e)}")
            return False
    
    async def _initialize_mock_sensor(self) -> bool:
        """Initialize mock fingerprint sensor for development."""
        try:
            self.sensor = "mock_sensor"
            self.template_count = len(self.mock_enrolled_users)
            self.is_initialized = True
            
            self.logger.info(f"Mock fingerprint sensor initialized: {self.template_count}/{self.max_templates} templates")
            return True
            
        except Exception as e:
            self.logger.error(f"Mock sensor initialization failed: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """
        Check if fingerprint sensor is available and initialized.
        
        Returns:
            True if available, False otherwise
        """
        return self.is_initialized
    
    async def verify_fingerprint(self, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify fingerprint against stored templates.
        
        Args:
            timeout: Optional timeout in seconds
            
        Returns:
            Dictionary with verification result
        """
        if not self.is_initialized:
            return {'success': False, 'error': 'Sensor not initialized'}
        
        timeout = timeout or self.timeout
        
        try:
            if self.mock_mode:
                return await self._mock_verify_fingerprint(timeout)
            else:
                return await self._real_verify_fingerprint(timeout)
                
        except Exception as e:
            self.logger.error(f"Fingerprint verification failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def _mock_verify_fingerprint(self, timeout: int) -> Dict[str, Any]:
        """Mock fingerprint verification for development."""
        self.logger.info("Mock fingerprint verification - place finger...")
        
        # Simulate waiting for finger
        await asyncio.sleep(2)
        
        # Simulate random verification result
        if random.random() > 0.2:  # 80% success rate
            # Random template from enrolled users
            if self.mock_enrolled_users:
                template_id = random.choice(list(self.mock_enrolled_users.keys()))
                user_info = self.mock_enrolled_users[template_id]
                
                return {
                    'success': True,
                    'verified': True,
                    'template_id': template_id,
                    'user_id': user_info['user_id'],
                    'confidence': random.uniform(0.85, 0.99),
                    'user_name': user_info.get('name', 'Unknown')
                }
            else:
                return {'success': False, 'error': 'No templates enrolled'}
        else:
            return {
                'success': True,
                'verified': False,
                'error': 'Fingerprint not recognized'
            }
    
    async def _real_verify_fingerprint(self, timeout: int) -> Dict[str, Any]:
        """Real fingerprint verification using AS608 sensor."""
        self.logger.info("Fingerprint verification - place finger...")
        
        try:
            start_time = time.time()
            
            # Wait for finger with timeout
            while not self.sensor.readImage():
                if time.time() - start_time > timeout:
                    return {'success': False, 'error': 'Verification timeout'}
                await asyncio.sleep(0.1)
            
            # Convert image to characteristics
            self.sensor.convertImage(0x01)
            
            # Search for matching template
            result = self.sensor.searchTemplate()
            position_number = result[0]
            accuracy_score = result[1]
            
            if position_number >= 0:
                # Calculate confidence from accuracy score
                confidence = min(accuracy_score / 100.0, 1.0)
                
                return {
                    'success': True,
                    'verified': True,
                    'template_id': position_number,
                    'confidence': confidence,
                    'accuracy_score': accuracy_score
                }
            else:
                return {
                    'success': True,
                    'verified': False,
                    'error': 'Fingerprint not recognized'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_template_count(self) -> int:
        """
        Get number of stored templates.
        
        Returns:
            Number of stored templates
        """
        return self.template_count
    
    def get_sensor_info(self) -> Dict[str, Any]:
        """
        Get fingerprint sensor information and status.
        
        Returns:
            Dictionary with sensor information
        """
        return {
            'initialized': self.is_initialized,
            'mock_mode': self.mock_mode,
            'template_count': self.template_count,
            'max_templates': self.max_templates,
            'uart_port': self.uart_port,
            'baudrate': self.baudrate,
            'timeout': self.timeout
        }
    
    def cleanup(self) -> None:
        """Clean up fingerprint sensor resources."""
        try:
            if self.sensor and not self.mock_mode:
                # Close sensor connection if needed
                pass
            
            self.is_initialized = False
            self.sensor = None
            
            self.logger.info("Fingerprint sensor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Fingerprint sensor cleanup error: {str(e)}")


# Global fingerprint manager instance
_fingerprint_manager = None


def get_fingerprint_manager() -> FingerprintManager:
    """Get the global fingerprint manager instance."""
    global _fingerprint_manager
    if _fingerprint_manager is None:
        _fingerprint_manager = FingerprintManager()
    return _fingerprint_manager