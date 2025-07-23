"""
Access Record Data Model for BioEntry Terminal
Defines the access record entity structure for attendance tracking.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


@dataclass
class AccessRecord:
    """
    Access record entity for the BioEntry terminal system.
    
    Represents a single access event (entry/exit) with verification details.
    """
    
    # Primary identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # User identification
    user_id: Optional[int] = None
    cedula: str = ""
    employee_name: str = ""
    
    # Access details
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    access_type: str = "entrada"  # 'entrada' | 'salida'
    
    # Verification details
    method: str = "offline"  # 'online' | 'offline'
    verification_type: str = "facial"  # 'facial' | 'fingerprint' | 'manual'
    confidence_score: Optional[float] = None
    
    # Device and location information
    device_id: str = ""
    location_name: str = "Terminal"
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    
    # System metadata
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_synced: bool = False
    sync_attempts: int = 0
    last_sync_attempt: Optional[str] = None
    server_record_id: Optional[str] = None
    
    # Additional metadata
    image_path: Optional[str] = None  # Path to captured image (if stored)
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate and normalize record data after initialization."""
        self.validate()
        self.normalize()
    
    def validate(self) -> None:
        """
        Validate access record data according to business rules.
        
        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if not self.cedula:
            raise ValueError("Cedula is required")
        
        if not self.employee_name:
            raise ValueError("Employee name is required")
        
        if not self.device_id:
            raise ValueError("Device ID is required")
        
        # Validate enum fields
        if self.access_type not in ['entrada', 'salida']:
            raise ValueError("Access type must be 'entrada' or 'salida'")
        
        if self.method not in ['online', 'offline']:
            raise ValueError("Method must be 'online' or 'offline'")
        
        if self.verification_type not in ['facial', 'fingerprint', 'manual']:
            raise ValueError("Verification type must be 'facial', 'fingerprint', or 'manual'")
        
        # Validate confidence score
        if self.confidence_score is not None:
            if not (0.0 <= self.confidence_score <= 1.0):
                raise ValueError("Confidence score must be between 0.0 and 1.0")
        
        # Validate timestamp format
        try:
            datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Invalid timestamp format")
    
    def normalize(self) -> None:
        """Normalize record data for consistency."""
        # Normalize names and locations
        self.employee_name = self.employee_name.strip().title()
        self.location_name = self.location_name.strip()
        
        # Normalize cedula
        self.cedula = self.cedula.strip()
        
        # Normalize device_id
        self.device_id = self.device_id.strip().upper()
        
        # Ensure access_type is lowercase
        self.access_type = self.access_type.lower()
        
        # Ensure method and verification_type are lowercase
        self.method = self.method.lower()
        self.verification_type = self.verification_type.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert record to dictionary format for database storage.
        
        Returns:
            Dictionary representation of access record
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'cedula': self.cedula,
            'employee_name': self.employee_name,
            'timestamp': self.timestamp,
            'access_type': self.access_type,
            'method': self.method,
            'verification_type': self.verification_type,
            'confidence_score': self.confidence_score,
            'device_id': self.device_id,
            'location_name': self.location_name,
            'location_lat': self.location_lat,
            'location_lng': self.location_lng,
            'created_at': self.created_at,
            'is_synced': self.is_synced,
            'sync_attempts': self.sync_attempts,
            'last_sync_attempt': self.last_sync_attempt,
            'server_record_id': self.server_record_id,
            'image_path': self.image_path,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccessRecord':
        """
        Create AccessRecord instance from dictionary data.
        
        Args:
            data: Dictionary with record data
            
        Returns:
            AccessRecord instance
        """
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            user_id=data.get('user_id'),
            cedula=data.get('cedula', ''),
            employee_name=data.get('employee_name', ''),
            timestamp=data.get('timestamp', datetime.utcnow().isoformat()),
            access_type=data.get('access_type', 'entrada'),
            method=data.get('method', 'offline'),
            verification_type=data.get('verification_type', 'facial'),
            confidence_score=data.get('confidence_score'),
            device_id=data.get('device_id', ''),
            location_name=data.get('location_name', 'Terminal'),
            location_lat=data.get('location_lat'),
            location_lng=data.get('location_lng'),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            is_synced=data.get('is_synced', False),
            sync_attempts=data.get('sync_attempts', 0),
            last_sync_attempt=data.get('last_sync_attempt'),
            server_record_id=data.get('server_record_id'),
            image_path=data.get('image_path'),
            notes=data.get('notes')
        )
    
    @classmethod
    def from_verification_response(cls, response, request, device_id: str) -> 'AccessRecord':
        """
        Create AccessRecord from verification service response.
        
        Args:
            response: VerificationResponse object
            request: VerificationRequest object  
            device_id: Terminal device identifier
            
        Returns:
            AccessRecord instance
        """
        return cls(
            id=response.record_id or str(uuid.uuid4()),
            user_id=response.user_data.get('id') if response.user_data else None,
            cedula=response.user_data.get('cedula') if response.user_data else request.cedula or '',
            employee_name=response.user_data.get('nombre') if response.user_data else 'Unknown',
            timestamp=response.timestamp,
            access_type=response.verification_type,
            method='online' if response.method_used == 'facial' else 'offline',
            verification_type=response.method_used,
            confidence_score=response.confidence,
            device_id=device_id,
            location_name=response.user_data.get('ubicacion', 'Terminal') if response.user_data else 'Terminal',
            location_lat=request.location[0] if request.location else None,
            location_lng=request.location[1] if request.location else None,
            is_synced=response.method_used == 'facial'  # Facial records are synced via API
        )
    
    def to_bulk_record_format(self) -> Dict[str, Any]:
        """
        Convert record to BulkRecord format for API upload.
        
        Returns:
            Dictionary in BulkRecord format
        """
        return {
            'user_id': self.user_id,
            'cedula': self.cedula,
            'employee_name': self.employee_name,
            'access_timestamp': self.timestamp,
            'method': self.method,
            'verification_type': self.verification_type,
            'confidence_score': self.confidence_score,
            'device_id': self.device_id,
            'location_name': self.location_name,
            'terminal_record_id': self.id,
            'created_at': self.created_at
        }
    
    def mark_as_synced(self, server_record_id: Optional[str] = None) -> None:
        """
        Mark record as successfully synchronized with server.
        
        Args:
            server_record_id: Optional server-side record ID
        """
        self.is_synced = True
        self.server_record_id = server_record_id
        self.last_sync_attempt = datetime.utcnow().isoformat()
    
    def increment_sync_attempts(self) -> None:
        """Increment sync attempt counter and update timestamp."""
        self.sync_attempts += 1
        self.last_sync_attempt = datetime.utcnow().isoformat()
    
    def is_entry(self) -> bool:
        """Check if this is an entry record."""
        return self.access_type == 'entrada'
    
    def is_exit(self) -> bool:
        """Check if this is an exit record."""
        return self.access_type == 'salida'
    
    def is_online_verification(self) -> bool:
        """Check if this was an online verification."""
        return self.method == 'online'
    
    def is_offline_verification(self) -> bool:
        """Check if this was an offline verification."""
        return self.method == 'offline'
    
    def get_display_info(self) -> Dict[str, str]:
        """
        Get record information formatted for UI display.
        
        Returns:
            Dictionary with display-friendly record information
        """
        # Parse timestamp for display
        try:
            dt = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M:%S")
            date_str = dt.strftime("%Y-%m-%d")
        except:
            time_str = "Unknown"
            date_str = "Unknown"
        
        # Format verification method
        method_map = {
            'facial': 'Reconocimiento Facial',
            'fingerprint': 'Huella Dactilar',
            'manual': 'Entrada Manual'
        }
        
        return {
            'empleado': self.employee_name,
            'cedula': self.cedula,
            'tipo': 'Entrada' if self.is_entry() else 'Salida',
            'hora': time_str,
            'fecha': date_str,
            'metodo': method_map.get(self.verification_type, self.verification_type),
            'confianza': f"{self.confidence_score:.1%}" if self.confidence_score else "N/A",
            'estado_sync': 'Sincronizado' if self.is_synced else 'Pendiente'
        }
    
    def get_age_minutes(self) -> int:
        """
        Get record age in minutes.
        
        Returns:
            Age in minutes from creation time
        """
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = now - created
            return int(delta.total_seconds() / 60)
        except:
            return 0
    
    def __str__(self) -> str:
        """String representation of access record."""
        return f"AccessRecord(cedula={self.cedula}, type={self.access_type}, method={self.verification_type})"
    
    def __repr__(self) -> str:
        """Detailed string representation of access record."""
        return (f"AccessRecord(id={self.id}, cedula={self.cedula}, "
                f"employee={self.employee_name}, type={self.access_type}, "
                f"method={self.verification_type}, synced={self.is_synced})")


def create_test_record(cedula: str = "12345678", 
                      employee_name: str = "Usuario Test",
                      device_id: str = "TERMINAL_001") -> AccessRecord:
    """
    Create a test access record for development and testing.
    
    Args:
        cedula: Test document ID
        employee_name: Test employee name
        device_id: Test device ID
        
    Returns:
        AccessRecord instance for testing
    """
    return AccessRecord(
        cedula=cedula,
        employee_name=employee_name,
        device_id=device_id,
        access_type="entrada",
        method="offline",
        verification_type="fingerprint",
        confidence_score=0.95,
        location_name="Terminal de Prueba"
    )


def create_entry_record(cedula: str, employee_name: str, 
                       verification_type: str = "facial",
                       confidence: float = 0.9,
                       device_id: str = "TERMINAL_001") -> AccessRecord:
    """
    Create an entry access record.
    
    Args:
        cedula: Employee document ID
        employee_name: Employee name
        verification_type: Type of verification used
        confidence: Confidence score
        device_id: Terminal device ID
        
    Returns:
        AccessRecord for entry
    """
    return AccessRecord(
        cedula=cedula,
        employee_name=employee_name,
        access_type="entrada",
        method="online" if verification_type == "facial" else "offline",
        verification_type=verification_type,
        confidence_score=confidence,
        device_id=device_id
    )


def create_exit_record(cedula: str, employee_name: str,
                      verification_type: str = "facial", 
                      confidence: float = 0.9,
                      device_id: str = "TERMINAL_001") -> AccessRecord:
    """
    Create an exit access record.
    
    Args:
        cedula: Employee document ID
        employee_name: Employee name
        verification_type: Type of verification used
        confidence: Confidence score
        device_id: Terminal device ID
        
    Returns:
        AccessRecord for exit
    """
    return AccessRecord(
        cedula=cedula,
        employee_name=employee_name,
        access_type="salida",
        method="online" if verification_type == "facial" else "offline",
        verification_type=verification_type,
        confidence_score=confidence,
        device_id=device_id
    )


if __name__ == "__main__":
    # Test access record model
    print("Testing AccessRecord model...")
    
    # Create test record
    record = create_test_record()
    print(f"Created record: {record}")
    
    # Test validation
    try:
        invalid_record = AccessRecord(cedula="", employee_name="")
        print("ERROR: Should have failed validation")
    except ValueError as e:
        print(f"Validation correctly failed: {e}")
    
    # Test dictionary conversion
    record_dict = record.to_dict()
    print(f"Record dict keys: {list(record_dict.keys())}")
    
    # Test from dictionary
    record_from_dict = AccessRecord.from_dict(record_dict)
    print(f"Record from dict: {record_from_dict}")
    
    # Test bulk record format
    bulk_format = record.to_bulk_record_format()
    print(f"Bulk format: {bulk_format}")
    
    # Test display info
    display_info = record.get_display_info()
    print(f"Display info: {display_info}")
    
    # Test entry/exit creation
    entry = create_entry_record("87654321", "Juan Pérez", "facial")
    exit_record = create_exit_record("87654321", "Juan Pérez", "fingerprint")
    print(f"Entry record: {entry}")
    print(f"Exit record: {exit_record}")
    
    # Test sync operations
    record.increment_sync_attempts()
    print(f"After sync attempt: attempts={record.sync_attempts}")
    
    record.mark_as_synced("server_123")
    print(f"After sync success: synced={record.is_synced}, server_id={record.server_record_id}")
    
    print("AccessRecord model tests completed successfully!")