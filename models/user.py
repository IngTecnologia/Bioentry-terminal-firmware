"""
User Data Model for BioEntry Terminal
Defines the user entity structure and validation methods.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
import re


@dataclass
class User:
    """
    User entity for the BioEntry terminal system.
    
    Represents a registered user with biometric and personal information.
    """
    
    # Primary identification
    id: Optional[int] = None
    employee_id: str = ""
    cedula: str = ""  # Document ID (primary identifier)
    
    # Personal information
    nombre: str = ""
    empresa: str = "principal"
    
    # Biometric data
    fingerprint_template_id: Optional[int] = None  # AS608 template slot (1-162)
    facial_reference_path: Optional[str] = None  # Path to reference image
    
    # System metadata
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_access: Optional[str] = None
    synced: bool = False  # Sync status with server
    
    # Additional data from server
    slot: Optional[int] = None  # Server-side slot assignment
    
    def __post_init__(self):
        """Validate and normalize user data after initialization."""
        self.validate()
        self.normalize()
    
    def validate(self) -> None:
        """
        Validate user data according to business rules.
        
        Raises:
            ValueError: If validation fails
        """
        # Validate cedula (document ID)
        if not self.cedula:
            raise ValueError("Cedula is required")
        
        if not self.cedula.isdigit():
            raise ValueError("Cedula must contain only digits")
        
        if len(self.cedula) < 6 or len(self.cedula) > 12:
            raise ValueError("Cedula must be between 6 and 12 digits")
        
        # Validate employee_id
        if not self.employee_id:
            raise ValueError("Employee ID is required")
        
        # Validate nombre
        if not self.nombre or len(self.nombre.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        
        # Validate fingerprint template ID range (AS608 sensor supports 1-162)
        if self.fingerprint_template_id is not None:
            if not (1 <= self.fingerprint_template_id <= 162):
                raise ValueError("Fingerprint template ID must be between 1 and 162")
    
    def normalize(self) -> None:
        """Normalize user data for consistency."""
        # Normalize names
        self.nombre = self.nombre.strip().title()
        self.empresa = self.empresa.strip().lower()
        
        # Normalize cedula (remove any spaces)
        self.cedula = self.cedula.replace(" ", "")
        
        # Normalize employee_id
        self.employee_id = self.employee_id.strip().upper()
        
        # Update timestamp
        self.updated_at = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert user to dictionary format for database storage.
        
        Returns:
            Dictionary representation of user data
        """
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'cedula': self.cedula,
            'nombre': self.nombre,
            'empresa': self.empresa,
            'fingerprint_template_id': self.fingerprint_template_id,
            'facial_reference_path': self.facial_reference_path,
            'is_active': self.is_active,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_access': self.last_access,
            'synced': self.synced,
            'slot': self.slot
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Create User instance from dictionary data.
        
        Args:
            data: Dictionary with user data
            
        Returns:
            User instance
        """
        return cls(
            id=data.get('id'),
            employee_id=data.get('employee_id', ''),
            cedula=data.get('cedula', ''),
            nombre=data.get('nombre', ''),
            empresa=data.get('empresa', 'principal'),
            fingerprint_template_id=data.get('fingerprint_template_id'),
            facial_reference_path=data.get('facial_reference_path'),
            is_active=data.get('is_active', True),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            updated_at=data.get('updated_at', datetime.utcnow().isoformat()),
            last_access=data.get('last_access'),
            synced=data.get('synced', False),
            slot=data.get('slot')
        )
    
    @classmethod
    def from_api_sync_data(cls, sync_data: Dict[str, Any]) -> 'User':
        """
        Create User instance from API sync response data.
        
        Args:
            sync_data: Compressed API sync data with short field names
            
        Returns:
            User instance
        """
        return cls(
            cedula=sync_data.get('c', ''),  # cedula
            nombre=sync_data.get('n', ''),  # nombre
            empresa=sync_data.get('e', 'principal'),  # empresa
            slot=sync_data.get('s'),  # slot
            employee_id=sync_data.get('c', ''),  # Use cedula as employee_id if not provided
            synced=True,  # Data from server is considered synced
            updated_at=datetime.utcnow().isoformat()
        )
    
    def update_last_access(self) -> None:
        """Update the last access timestamp."""
        self.last_access = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
    
    def mark_as_synced(self) -> None:
        """Mark user as synchronized with server."""
        self.synced = True
        self.updated_at = datetime.utcnow().isoformat()
    
    def has_fingerprint(self) -> bool:
        """Check if user has fingerprint template registered."""
        return self.fingerprint_template_id is not None
    
    def has_facial_reference(self) -> bool:
        """Check if user has facial reference image."""
        return self.facial_reference_path is not None
    
    def get_display_info(self) -> Dict[str, str]:
        """
        Get user information formatted for UI display.
        
        Returns:
            Dictionary with display-friendly user information
        """
        return {
            'nombre': self.nombre,
            'cedula': self.cedula,
            'empresa': self.empresa.title(),
            'estado': 'Activo' if self.is_active else 'Inactivo',
            'biometrics': 'Huella' if self.has_fingerprint() else 'Facial' if self.has_facial_reference() else 'Manual'
        }
    
    def __str__(self) -> str:
        """String representation of user."""
        return f"User(cedula={self.cedula}, nombre={self.nombre}, empresa={self.empresa})"
    
    def __repr__(self) -> str:
        """Detailed string representation of user."""
        return (f"User(id={self.id}, cedula={self.cedula}, nombre={self.nombre}, "
                f"empresa={self.empresa}, active={self.is_active}, synced={self.synced})")


def validate_cedula_format(cedula: str) -> bool:
    """
    Validate cedula format according to business rules.
    
    Args:
        cedula: Document ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not cedula:
        return False
    
    # Remove any spaces
    cedula = cedula.replace(" ", "")
    
    # Check if it contains only digits
    if not cedula.isdigit():
        return False
    
    # Check length (6-12 digits)
    if len(cedula) < 6 or len(cedula) > 12:
        return False
    
    return True


def create_test_user(cedula: str = "12345678", nombre: str = "Usuario Test") -> User:
    """
    Create a test user for development and testing.
    
    Args:
        cedula: Test document ID
        nombre: Test user name
        
    Returns:
        User instance for testing
    """
    return User(
        employee_id=f"EMP_{cedula}",
        cedula=cedula,
        nombre=nombre,
        empresa="test",
        is_active=True,
        fingerprint_template_id=1,  # Assign first template slot for testing
        synced=False
    )


if __name__ == "__main__":
    # Test user model
    print("Testing User model...")
    
    # Create test user
    user = create_test_user()
    print(f"Created user: {user}")
    
    # Test validation
    try:
        invalid_user = User(cedula="", nombre="")
        print("ERROR: Should have failed validation")
    except ValueError as e:
        print(f"Validation correctly failed: {e}")
    
    # Test dictionary conversion
    user_dict = user.to_dict()
    print(f"User dict: {user_dict}")
    
    # Test from dictionary
    user_from_dict = User.from_dict(user_dict)
    print(f"User from dict: {user_from_dict}")
    
    # Test API sync data
    sync_data = {'c': '87654321', 'n': 'Juan Pérez', 'e': 'empresa_abc', 's': 5}
    user_from_sync = User.from_api_sync_data(sync_data)
    print(f"User from sync: {user_from_sync}")
    
    # Test display info
    display_info = user.get_display_info()
    print(f"Display info: {display_info}")
    
    print("User model tests completed successfully!")