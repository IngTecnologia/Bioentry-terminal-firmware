"""
Proximity Manager for BioEntry Terminal
Handles APDS-9930 proximity sensor for automatic user detection.
"""

import asyncio
import time
import random
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from utils.config import get_config
from utils.logger import get_logger


class ProximityManager:
    """
    Proximity manager for APDS-9930 sensor communication.
    
    Supports both real hardware (APDS-9930 via I2C) and mock mode for development.
    Detects user presence to automatically activate the terminal.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Hardware configuration
        self.i2c_address = self.config.hardware.proximity_i2c_address
        self.threshold = self.config.hardware.proximity_threshold
        
        # Sensor state
        self.sensor = None
        self.is_initialized = False
        self.is_monitoring = False
        self.last_reading = 0
        self.detection_callback = None
        
        # Mock mode detection
        self.mock_mode = self.config.is_mock_mode() or not self.config.hardware.proximity_enabled
        
        # Mock simulation state
        self.mock_detection_active = False
        self.mock_cycle_count = 0
        
        self.logger.info(f"Proximity manager initialized - Mock mode: {self.mock_mode}")
    
    async def initialize(self) -> bool:
        """
        Initialize proximity sensor hardware or mock sensor.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if self.mock_mode:
                return await self._initialize_mock_sensor()
            else:
                return await self._initialize_real_sensor()
        except Exception as e:
            self.logger.error(f"Proximity sensor initialization failed: {str(e)}")
            return False
    
    async def _initialize_real_sensor(self) -> bool:
        """Initialize real APDS-9930 proximity sensor."""
        try:
            # Try to import I2C library
            import board
            import busio
            import adafruit_apds9960
            
            # Initialize I2C bus
            i2c = busio.I2C(board.SCL, board.SDA)
            
            # Initialize APDS-9930 sensor
            self.sensor = adafruit_apds9960.APDS9960(i2c)
            
            # Enable proximity detection
            self.sensor.enable_proximity = True
            
            # Set proximity threshold
            if hasattr(self.sensor, 'proximity_interrupt_threshold'):
                self.sensor.proximity_interrupt_threshold = self.threshold
            
            self.is_initialized = True
            self.logger.info(f"APDS-9930 sensor initialized with threshold {self.threshold}")
            return True
            
        except ImportError:
            self.logger.error("APDS-9930 library not available")
            return False
        except Exception as e:
            self.logger.error(f"Real sensor initialization failed: {str(e)}")
            return False
    
    async def _initialize_mock_sensor(self) -> bool:
        """Initialize mock proximity sensor for development."""
        try:
            self.sensor = "mock_sensor"
            self.is_initialized = True
            
            self.logger.info(f"Mock proximity sensor initialized with threshold {self.threshold}")
            return True
            
        except Exception as e:
            self.logger.error(f"Mock sensor initialization failed: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """
        Check if proximity sensor is available and initialized.
        
        Returns:
            True if available, False otherwise
        """
        return self.is_initialized
    
    def read_proximity(self) -> Optional[int]:
        """
        Read current proximity value from sensor.
        
        Returns:
            Proximity value (0-255), or None if read failed
        """
        if not self.is_initialized:
            return None
        
        try:
            if self.mock_mode:
                return self._mock_read_proximity()
            else:
                return self._real_read_proximity()
                
        except Exception as e:
            self.logger.error(f"Proximity read failed: {str(e)}")
            return None
    
    def _mock_read_proximity(self) -> int:
        """Mock proximity reading for development."""
        # Simulate cyclical proximity detection
        self.mock_cycle_count += 1
        
        # Create a detection cycle every 20 readings (about 20 seconds)
        cycle_position = self.mock_cycle_count % 100
        
        if 20 <= cycle_position <= 35:
            # User approaching
            proximity = int(self.threshold + random.randint(10, 50))
            self.mock_detection_active = True
        elif 35 < cycle_position <= 50:
            # User present
            proximity = int(self.threshold + random.randint(50, 100))
            self.mock_detection_active = True
        elif 50 < cycle_position <= 65:
            # User leaving
            proximity = int(self.threshold + random.randint(-10, 30))
            self.mock_detection_active = True
        else:
            # No user
            proximity = random.randint(10, self.threshold - 10)
            self.mock_detection_active = False
        
        self.last_reading = proximity
        return proximity
    
    def _real_read_proximity(self) -> Optional[int]:
        """Real proximity reading from APDS-9930 sensor."""
        try:
            proximity = self.sensor.proximity
            self.last_reading = proximity
            return proximity
        except Exception as e:
            self.logger.error(f"Real proximity read error: {str(e)}")
            return None
    
    def is_user_detected(self, proximity_value: Optional[int] = None) -> bool:
        """
        Check if user is detected based on proximity value.
        
        Args:
            proximity_value: Optional proximity value, reads current if None
            
        Returns:
            True if user detected, False otherwise
        """
        if proximity_value is None:
            proximity_value = self.read_proximity()
        
        if proximity_value is None:
            return False
        
        return proximity_value >= self.threshold
    
    async def start_monitoring(self, detection_callback: Optional[Callable[[bool], None]] = None) -> bool:
        """
        Start continuous proximity monitoring.
        
        Args:
            detection_callback: Optional callback function called on detection state change
            
        Returns:
            True if monitoring started successfully, False otherwise
        """
        if not self.is_initialized:
            if not await self.initialize():
                return False
        
        if self.is_monitoring:
            return True
        
        self.detection_callback = detection_callback
        self.is_monitoring = True
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
        self.logger.info("Proximity monitoring started")
        return True
    
    async def _monitoring_loop(self):
        """Background monitoring loop for proximity detection."""
        last_detection_state = False
        detection_start_time = None
        stable_detection_delay = 0.5  # Require stable detection for 500ms
        
        while self.is_monitoring:
            try:
                proximity = self.read_proximity()
                
                if proximity is not None:
                    current_detection = self.is_user_detected(proximity)
                    
                    # Check for state change
                    if current_detection != last_detection_state:
                        if current_detection:
                            # User detected - start stability timer  
                            detection_start_time = time.time()
                        else:
                            # User no longer detected
                            detection_start_time = None
                            if self.detection_callback:
                                self.detection_callback(False)
                            self.logger.debug("User left proximity")
                        
                        last_detection_state = current_detection
                    
                    # Check for stable detection
                    elif current_detection and detection_start_time:
                        if time.time() - detection_start_time >= stable_detection_delay:
                            if self.detection_callback:
                                self.detection_callback(True)
                            self.logger.info(f"User detected (proximity: {proximity})")
                            detection_start_time = None  # Prevent multiple callbacks
                
                # Sleep before next reading (10Hz monitoring)
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Proximity monitoring error: {str(e)}")
                await asyncio.sleep(1)  # Longer sleep on error
    
    def stop_monitoring(self) -> None:
        """Stop proximity monitoring."""
        self.is_monitoring = False
        self.detection_callback = None
        self.logger.info("Proximity monitoring stopped")
    
    def get_sensor_info(self) -> Dict[str, Any]:
        """
        Get proximity sensor information and status.
        
        Returns:
            Dictionary with sensor information
        """
        return {
            'initialized': self.is_initialized,
            'monitoring': self.is_monitoring,
            'mock_mode': self.mock_mode,
            'i2c_address': hex(self.i2c_address),
            'threshold': self.threshold,
            'last_reading': self.last_reading,
            'user_detected': self.is_user_detected()
        }
    
    def cleanup(self) -> None:
        """Clean up proximity sensor resources."""
        try:
            self.stop_monitoring()
            
            if self.sensor and not self.mock_mode:
                # Disable proximity detection
                if hasattr(self.sensor, 'enable_proximity'):
                    self.sensor.enable_proximity = False
            
            self.is_initialized = False
            self.sensor = None
            
            self.logger.info("Proximity sensor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Proximity sensor cleanup error: {str(e)}")


# Global proximity manager instance
_proximity_manager = None


def get_proximity_manager() -> ProximityManager:
    """Get the global proximity manager instance."""
    global _proximity_manager
    if _proximity_manager is None:
        _proximity_manager = ProximityManager()
    return _proximity_manager