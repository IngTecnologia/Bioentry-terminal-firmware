import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class HardwareConfig:
    """Hardware configuration for the terminal"""
    camera_enabled: bool = True
    camera_resolution: tuple = (640, 480)
    camera_fps: int = 15
    camera_rotation: int = 0
    
    fingerprint_enabled: bool = True
    fingerprint_uart_port: str = "/dev/serial0"
    fingerprint_baudrate: int = 57600
    fingerprint_timeout: int = 5
    
    proximity_enabled: bool = True
    proximity_i2c_address: int = 0x39
    proximity_threshold: int = 100
    
    audio_enabled: bool = True
    audio_volume: int = 80
    
    display_brightness: int = 80
    display_timeout: int = 60


@dataclass
class ApiConfig:
    """Server API configuration"""
    base_url: str = "http://localhost:8000"
    terminal_id: str = "TERMINAL_001"
    api_key: str = "terminal_key_001"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1


@dataclass
class DatabaseConfig:
    """Local database configuration"""
    path: str = "data/database.db"
    backup_interval: int = 3600  # 1 hour in seconds
    max_records: int = 10000
    cleanup_days: int = 30


@dataclass
class OperationConfig:
    """Terminal operation configuration"""
    mode: str = "hybrid"  # hybrid, online_only, offline_only
    max_facial_attempts: int = 3
    max_fingerprint_attempts: int = 3
    timeout_seconds: int = 30
    auto_sync_interval: int = 300  # 5 minutes
    detection_interval: int = 3  # Detect every 3 frames
    
    # Location configuration
    location_name: str = "Terminal Principal"
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_radius: int = 200


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file_path: str = "data/logs/terminal.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ConfigManager:
    """Centralized configuration manager"""
    
    def __init__(self, config_file: str = "data/config.json"):
        self.config_file = Path(config_file)
        self.config_dir = self.config_file.parent
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Default configurations
        self.hardware = HardwareConfig()
        self.api = ApiConfig()
        self.database = DatabaseConfig()
        self.operation = OperationConfig()
        self.logging = LoggingConfig()
        
        # Load configuration from file
        self.load_config()
        
        # Load environment variables
        self.load_environment_variables()
    
    def load_config(self) -> None:
        """Load configuration from JSON file"""
        if not self.config_file.exists():
            self.save_config()  # Create file with default values
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Update configurations
            if 'hardware' in config_data:
                self._update_dataclass(self.hardware, config_data['hardware'])
            
            if 'api' in config_data:
                self._update_dataclass(self.api, config_data['api'])
            
            if 'database' in config_data:
                self._update_dataclass(self.database, config_data['database'])
            
            if 'operation' in config_data:
                self._update_dataclass(self.operation, config_data['operation'])
            
            if 'logging' in config_data:
                self._update_dataclass(self.logging, config_data['logging'])
                
        except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
            print(f"Error loading configuration: {e}")
            print("Using default configuration")
    
    def load_environment_variables(self) -> None:
        """Load configurations from environment variables"""
        # Hardware
        if os.getenv("MOCK_HARDWARE"):
            self.hardware.camera_enabled = not bool(os.getenv("MOCK_CAMERA"))
            self.hardware.fingerprint_enabled = not bool(os.getenv("MOCK_FINGERPRINT"))
            self.hardware.proximity_enabled = not bool(os.getenv("MOCK_PROXIMITY"))
        
        # API
        if os.getenv("API_BASE_URL"):
            self.api.base_url = os.getenv("API_BASE_URL")
        
        if os.getenv("TERMINAL_ID"):
            self.api.terminal_id = os.getenv("TERMINAL_ID")
        
        if os.getenv("API_KEY"):
            self.api.api_key = os.getenv("API_KEY")
        
        # Database
        if os.getenv("DATABASE_PATH"):
            self.database.path = os.getenv("DATABASE_PATH")
        
        # Logging
        if os.getenv("LOG_LEVEL"):
            self.logging.level = os.getenv("LOG_LEVEL")
        
        if os.getenv("DEBUG_MODE"):
            self.logging.level = "DEBUG"
    
    def save_config(self) -> None:
        """Save current configuration to JSON file"""
        config_data = {
            'hardware': self._dataclass_to_dict(self.hardware),
            'api': self._dataclass_to_dict(self.api),
            'database': self._dataclass_to_dict(self.database),
            'operation': self._dataclass_to_dict(self.operation),
            'logging': self._dataclass_to_dict(self.logging)
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def update_config(self, section: str, updates: Dict[str, Any]) -> None:
        """Update a specific configuration section"""
        if section == 'hardware':
            self._update_dataclass(self.hardware, updates)
        elif section == 'api':
            self._update_dataclass(self.api, updates)
        elif section == 'database':
            self._update_dataclass(self.database, updates)
        elif section == 'operation':
            self._update_dataclass(self.operation, updates)
        elif section == 'logging':
            self._update_dataclass(self.logging, updates)
        else:
            raise ValueError(f"Unknown configuration section: {section}")
        
        self.save_config()
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return {
            'hardware': self._dataclass_to_dict(self.hardware),
            'api': self._dataclass_to_dict(self.api),
            'database': self._dataclass_to_dict(self.database),
            'operation': self._dataclass_to_dict(self.operation),
            'logging': self._dataclass_to_dict(self.logging)
        }
    
    def is_mock_mode(self) -> bool:
        """Determine if in mock mode for development"""
        return bool(os.getenv("MOCK_HARDWARE")) or bool(os.getenv("DEBUG_MODE"))
    
    def get_full_database_path(self) -> Path:
        """Get full database path"""
        if self.database.path.startswith('/'):
            return Path(self.database.path)
        else:
            return Path(__file__).parent.parent / self.database.path
    
    def get_full_log_path(self) -> Path:
        """Get full log file path"""
        if self.logging.file_path.startswith('/'):
            return Path(self.logging.file_path)
        else:
            return Path(__file__).parent.parent / self.logging.file_path
    
    def _update_dataclass(self, dataclass_instance, updates: Dict[str, Any]) -> None:
        """Update a dataclass with new values"""
        for key, value in updates.items():
            if hasattr(dataclass_instance, key):
                setattr(dataclass_instance, key, value)
    
    def _dataclass_to_dict(self, dataclass_instance) -> Dict[str, Any]:
        """Convert a dataclass to dictionary"""
        return {
            field: getattr(dataclass_instance, field)
            for field in dataclass_instance.__dataclass_fields__
        }


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config_manager


def reload_config() -> None:
    """Reload configuration from file"""
    global config_manager
    config_manager.load_config()


if __name__ == "__main__":
    # Test configuration
    config = get_config()
    print("Configuration loaded:")
    print(json.dumps(config.get_config_dict(), indent=2))
    
    # Test mock mode
    print(f"\nMock mode: {config.is_mock_mode()}")
    
    # Test paths
    print(f"DB path: {config.get_full_database_path()}")
    print(f"Log path: {config.get_full_log_path()}")