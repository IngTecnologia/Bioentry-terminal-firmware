# BioEntry Terminal API Integration Documentation

## Overview

This document provides comprehensive documentation for the BioEntry Terminal API integration. This integration enables the terminal to communicate with the FastAPI backend server for facial verification, user synchronization, and records management.

**IMPORTANT**: This documentation is designed to enable future development without access to the API codebase. All endpoints, data formats, authentication methods, and integration patterns are fully documented here.

## Table of Contents

1. [API Architecture](#api-architecture)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Data Structures](#data-structures)
5. [Integration Services](#integration-services)
6. [Error Handling](#error-handling)
7. [Configuration](#configuration)
8. [Testing and Development](#testing-and-development)

---

## API Architecture

### Base Configuration

- **Base URL**: `http://localhost:8000` (configurable)
- **Protocol**: HTTP/HTTPS with REST API
- **Data Format**: JSON
- **Authentication**: API Key based
- **Timeout**: 30 seconds (configurable)
- **Retry Logic**: 3 attempts with exponential backoff

### Terminal Architecture

The terminal operates in **hybrid online/offline mode**:

- **Online Mode**: Uses API for facial verification and data sync
- **Offline Mode**: Uses local fingerprint verification and queues records for later sync
- **Fallback Mode**: Manual entry when biometrics unavailable

---

## Authentication

### API Key Authentication

All terminal requests use API key authentication via headers:

```http
X-API-Key: terminal_key_001
Accept: application/json
Content-Type: application/json (for JSON requests)
```

### Terminal Identification

Each terminal is identified by a unique `terminal_id`:
- **Format**: `TERMINAL_001`, `TERMINAL_002`, etc.
- **Usage**: Included in all requests for terminal-specific operations
- **Configuration**: Stored in terminal config file

### API Key Configuration

API keys are configured on the server side in `config.py`:

```python
API_KEYS: Dict[str, str] = {
    "TERMINAL_001": "terminal_key_001",
    "TERMINAL_002": "terminal_key_002"
}
```

---

## API Endpoints

### 1. Health and Connectivity

#### GET `/terminal-health/{terminal_id}`

**Purpose**: Check terminal connectivity and server health.

**Parameters**:
- `terminal_id` (path): Terminal identifier

**Response** (200 OK):
```json
{
  "status": "healthy",
  "terminal_id": "TERMINAL_001",
  "server_time": "2024-01-15T10:30:00Z",
  "api_version": "1.0.0"
}
```

**Usage**: Called every 30 seconds for connectivity monitoring.

---

### 2. Facial Verification

#### POST `/verify-terminal/auto` (Primary Method)

**Purpose**: Automatic facial verification - identifies user and detects entry/exit type.

**Headers**:
```http
X-API-Key: terminal_key_001
```

**Request Body** (multipart/form-data):
```
image: (binary data, JPEG format)
terminal_id: "TERMINAL_001"
lat: 40.7128 (optional)
lng: -74.0060 (optional)
```

**Response** (200 OK):
```json
{
  "verified": true,
  "distance": 0.23,
  "cedula": "12345678",
  "nombre": "Juan Pérez",
  "tipo_registro": "entrada",
  "record_id": "rec_12345",
  "timestamp": "2024-01-15T10:30:00Z",
  "ubicacion": "Terminal Principal",
  "mensaje": "Acceso autorizado",
  "fuera_de_ubicacion": false,
  "distancia_ubicacion": 0
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "Usuario no reconocido o fuera de ubicación permitida"
}
```

#### POST `/verify-terminal` (Manual Method)

**Purpose**: Manual facial verification with known cedula.

**Request Body** (multipart/form-data):
```
image: (binary data, JPEG format)
cedula: "12345678"
terminal_id: "TERMINAL_001"
tipo_registro: "entrada" | "salida"
lat: 40.7128 (optional)
lng: -74.0060 (optional)
```

**Response**: Same format as automatic verification.

---

### 3. User Database Synchronization

#### GET `/terminal-sync/{terminal_id}`

**Purpose**: Download user database for offline operation.

**Parameters**:
- `terminal_id` (path): Terminal identifier
- `last_sync` (query, optional): ISO timestamp of last sync

**Response** (200 OK):
```json
{
  "sync_timestamp": "2024-01-15T10:30:00Z",
  "total_records": 150,
  "records": [
    {
      "c": "12345678",    // cedula (compressed field name)
      "n": "Juan Pérez",  // nombre (compressed field name)
      "e": "Empresa ABC", // empresa (compressed field name)
      "s": 1              // slot (compressed field name)
    }
  ]
}
```

#### GET `/terminal-sync/{terminal_id}/check`

**Purpose**: Check if synchronization is needed (fast endpoint).

**Response** (200 OK):
```json
{
  "needs_sync": true,
  "last_server_update": "2024-01-15T09:00:00Z",
  "total_users": 150
}
```

---

### 4. Records Upload

#### POST `/terminal-records/bulk`

**Purpose**: Upload multiple access records in batch.

**Request Body** (JSON):
```json
{
  "terminal_id": "TERMINAL_001",
  "sync_timestamp": "2024-01-15T10:30:00Z",
  "records": [
    {
      "user_id": 123,
      "cedula": "12345678",
      "employee_name": "Juan Pérez",
      "access_timestamp": "2024-01-15T08:30:00Z",
      "method": "offline",
      "verification_type": "fingerprint",
      "confidence_score": 0.95,
      "device_id": "TERMINAL_001",
      "location_name": "Terminal Principal",
      "terminal_record_id": "local_rec_001",
      "created_at": "2024-01-15T08:30:00Z"
    }
  ]
}
```

**Response** (200 OK):
```json
{
  "summary": {
    "total_received": 1,
    "processed_successfully": 1,
    "failed": 0
  },
  "processed_records": [
    {
      "terminal_record_id": "local_rec_001",
      "server_record_id": "srv_rec_456",
      "status": "created"
    }
  ],
  "failed_records": []
}
```

#### GET `/terminal-records/status/{terminal_id}`

**Purpose**: Get record statistics for terminal.

**Response** (200 OK):
```json
{
  "terminal_id": "TERMINAL_001",
  "total_records": 245,
  "last_record": "2024-01-15T10:30:00Z",
  "sync_status": "up_to_date"
}
```

---

### 5. Terminal Configuration

#### GET `/terminal-config/{terminal_id}`

**Purpose**: Retrieve terminal-specific configuration.

**Response** (200 OK):
```json
{
  "config": {
    "terminal_id": "TERMINAL_001",
    "location": {
      "name": "Terminal Principal",
      "lat": 40.7128,
      "lng": -74.0060,
      "radius": 200
    },
    "hardware": {
      "camera_enabled": true,
      "fingerprint_enabled": true,
      "proximity_enabled": true
    },
    "operation": {
      "mode": "hybrid",
      "max_attempts": 3,
      "timeout_seconds": 30
    },
    "display": {
      "brightness": 80,
      "timeout": 60
    },
    "sync": {
      "interval_minutes": 5,
      "batch_size": 50
    }
  }
}
```

---

## Data Structures

### Core Data Classes

#### APIResponse
```python
@dataclass
class APIResponse:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
```

#### VerificationResult
```python
@dataclass
class VerificationResult:
    verified: bool
    distance: float
    cedula: str
    nombre: str
    tipo_registro: str  # 'entrada' | 'salida'
    record_id: str
    timestamp: str
    ubicacion: str
    mensaje: str
    fuera_de_ubicacion: bool = False
    distancia_ubicacion: int = 0
```

#### BulkRecord
```python
@dataclass
class BulkRecord:
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
```

#### TerminalConfig
```python
@dataclass
class TerminalConfig:
    terminal_id: str
    location: Dict[str, Any]
    hardware: Dict[str, bool]
    operation: Dict[str, Any]
    display: Dict[str, Any]
    sync: Dict[str, Any]
```

---

## Integration Services

### 1. APIClient Service (`services/api_client.py`)

**Purpose**: Handles all HTTP communication with the API server.

**Key Features**:
- Automatic retry logic with exponential backoff
- Connection state monitoring
- Request/response logging
- Error handling and classification

**Main Methods**:

```python
class APIClient:
    async def check_connectivity(self) -> bool
    async def get_health_status(self) -> APIResponse
    async def get_terminal_config(self) -> APIResponse
    async def verify_face_automatic(self, image_bytes: bytes, lat: Optional[float] = None, lng: Optional[float] = None) -> APIResponse
    async def verify_face_manual(self, cedula: str, image_bytes: bytes, tipo_registro: str, lat: Optional[float] = None, lng: Optional[float] = None) -> APIResponse
    async def sync_user_database(self, last_sync: Optional[str] = None) -> APIResponse
    async def check_sync_status(self) -> APIResponse
    async def upload_bulk_records(self, records: List[BulkRecord]) -> APIResponse
    async def get_records_status(self) -> APIResponse
```

**Usage Example**:
```python
api_client = get_api_client()

# Check connectivity
is_online = await api_client.check_connectivity()

# Verify face automatically
response = await api_client.verify_face_automatic(image_bytes)
if response.success:
    result = api_client.parse_verification_result(response)
```

### 2. VerificationService (`services/verification_service.py`)

**Purpose**: Orchestrates all verification methods with automatic fallback.

**Key Features**:
- Unified interface for facial, fingerprint, and manual verification
- Automatic fallback between methods
- Online/offline mode handling
- Local record creation

**Main Methods**:

```python
class VerificationService:
    async def verify_user(self, request: VerificationRequest) -> VerificationResponse
    async def verify_with_fallback(self, primary_request: VerificationRequest) -> VerificationResponse
    def prepare_image_for_verification(self, image: Union[np.ndarray, bytes]) -> bytes
    def validate_image_quality(self, image_bytes: bytes) -> Dict[str, Any]
```

**Usage Example**:
```python
verification_service = get_verification_service()

# Prepare verification request
request = VerificationRequest(
    method='facial',
    image_data=image_bytes,
    location=(lat, lng)
)

# Perform verification with fallback
response = await verification_service.verify_with_fallback(request)
```

### 3. SyncService (`services/sync_service.py`)

**Purpose**: Manages bidirectional data synchronization.

**Key Features**:
- Automatic sync scheduling
- Batch record uploads
- User database downloads
- Retry logic for failed syncs
- Sync status tracking

**Main Methods**:

```python
class SyncService:
    async def start_auto_sync(self)
    async def stop_auto_sync(self)
    async def perform_full_sync(self) -> Dict[str, Any]
    async def sync_users_from_server(self) -> Dict[str, Any]
    async def sync_records_to_server(self) -> Dict[str, Any]
    async def force_user_sync(self) -> Dict[str, Any]
    async def force_records_sync(self) -> Dict[str, Any]
```

**Usage Example**:
```python
sync_service = get_sync_service()

# Start automatic synchronization
await sync_service.start_auto_sync()

# Force immediate sync
result = await sync_service.perform_full_sync()
```

---

## Error Handling

### HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid request parameters or authentication failure
- **403 Forbidden**: Invalid API key
- **404 Not Found**: Endpoint or resource not found
- **500 Internal Server Error**: Server-side error

### Error Response Format

```json
{
  "detail": "Error message description"
}
```

### Common Error Scenarios

1. **Network Connectivity Issues**:
   - Automatic retry with exponential backoff
   - Graceful fallback to offline mode
   - Status tracking and recovery

2. **Authentication Errors**:
   - API key validation failure
   - Terminal ID not recognized
   - Immediate failure (no retry)

3. **Verification Failures**:
   - User not recognized
   - Outside allowed location
   - Poor image quality
   - Fallback to alternative methods

4. **Sync Errors**:
   - Partial sync completion
   - Record format validation
   - Conflict resolution

### Error Handling Patterns

```python
try:
    response = await api_client.verify_face_automatic(image_bytes)
    if response.success:
        result = api_client.parse_verification_result(response)
        # Handle successful verification
    else:
        # Handle API error
        logger.error(f"Verification failed: {response.error}")
        # Attempt fallback method
except Exception as e:
    # Handle network/system error
    logger.error(f"System error: {str(e)}")
    # Switch to offline mode
```

---

## Configuration

### API Configuration (`utils/config.py`)

```python
@dataclass
class ApiConfig:
    base_url: str = "http://localhost:8000"
    terminal_id: str = "TERMINAL_001"
    api_key: str = "terminal_key_001"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 2
    health_check_interval: int = 30
    connection_timeout: int = 5
    
    # Endpoint mappings
    endpoints: Dict[str, str] = field(default_factory=lambda: {
        "health": "/terminal-health/{terminal_id}",
        "config": "/terminal-config/{terminal_id}",
        "verify_manual": "/verify-terminal",
        "verify_auto": "/verify-terminal/auto",
        "sync_users": "/terminal-sync/{terminal_id}",
        "sync_check": "/terminal-sync/{terminal_id}/check",
        "bulk_records": "/terminal-records/bulk",
        "records_status": "/terminal-records/status/{terminal_id}"
    })
```

### Sync Configuration

```python
@dataclass
class SyncConfig:
    interval_minutes: int = 5
    batch_size: int = 50
    max_retry_attempts: int = 5
    retry_delay_seconds: int = 30
    user_sync_enabled: bool = True
    records_sync_enabled: bool = True
```

### Environment Variables

```bash
# API Configuration
API_BASE_URL=http://localhost:8000
TERMINAL_ID=TERMINAL_001
API_KEY=terminal_key_001

# Development/Testing
MOCK_HARDWARE=true
DEBUG_MODE=true
```

---

## Testing and Development

### Mock API Server

For development without the actual API server, create a mock server:

```python
# mock_api_server.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/terminal-health/{terminal_id}")
async def health_check(terminal_id: str):
    return {"status": "healthy", "terminal_id": terminal_id}

@app.post("/verify-terminal/auto")
async def verify_auto():
    return {
        "verified": True,
        "distance": 0.25,
        "cedula": "12345678",
        "nombre": "Test User",
        "tipo_registro": "entrada",
        "record_id": "test_001",
        "timestamp": "2024-01-15T10:30:00Z",
        "ubicacion": "Test Terminal",
        "mensaje": "Test verification"
    }

# Run with: uvicorn mock_api_server:app --port 8000
```

### API Client Testing

```python
# Test API connectivity
async def test_api_integration():
    api_client = get_api_client()
    
    # Test health
    health = await api_client.get_health_status()
    print(f"Health: {health}")
    
    # Test sync
    sync_result = await api_client.sync_user_database()
    print(f"Sync: {sync_result}")
    
    # Test verification (with mock image)
    test_image = create_test_image()
    verify_result = await api_client.verify_face_automatic(test_image)
    print(f"Verification: {verify_result}")

asyncio.run(test_api_integration())
```

### Integration Testing

```bash
# Start mock API server
uvicorn mock_api_server:app --port 8000 &

# Set environment for testing
export API_BASE_URL=http://localhost:8000
export MOCK_HARDWARE=true

# Run terminal services
python -m services.api_client
python -m services.verification_service
python -m services.sync_service
```

---

## Implementation Checklist

### ✅ Completed Components

1. **APIClient** (`services/api_client.py`):
   - ✅ All endpoint implementations
   - ✅ Retry logic with exponential backoff
   - ✅ Connection monitoring
   - ✅ Response parsing utilities
   - ✅ Error handling patterns

2. **VerificationService** (`services/verification_service.py`):
   - ✅ Unified verification interface
   - ✅ Automatic fallback mechanisms
   - ✅ Online/offline mode handling
   - ✅ Image processing utilities
   - ✅ Local record creation

3. **SyncService** (`services/sync_service.py`):
   - ✅ Automatic sync scheduling
   - ✅ Bidirectional synchronization
   - ✅ Batch record uploads
   - ✅ User database downloads
   - ✅ Retry logic and status tracking

4. **Configuration** (`utils/config.py`):
   - ✅ Complete API configuration
   - ✅ Endpoint mappings
   - ✅ Environment variable support
   - ✅ Sync configuration parameters

### 🔄 Integration Points

- **State Manager**: API services integrate with system state transitions
- **Database Manager**: Local data persistence with sync queue management
- **UI System**: Status updates and error displays
- **Hardware Managers**: Camera integration for image capture

### 📋 Usage in Main Application

```python
# main.py - Integration example
async def main():
    # Initialize services
    api_client = get_api_client()
    verification_service = get_verification_service()
    sync_service = get_sync_service()
    
    # Start background services
    await sync_service.start_auto_sync()
    
    # Main application loop
    while True:
        # Handle verification requests
        if state_manager.current_state == SystemState.VERIFYING:
            # Capture image from camera
            image_data = camera_manager.capture_image()
            
            # Create verification request
            request = VerificationRequest(
                method='facial',
                image_data=image_data
            )
            
            # Perform verification with fallback
            response = await verification_service.verify_with_fallback(request)
            
            # Handle result
            if response.verified:
                state_manager.set_state(SystemState.ACCESS_GRANTED, StateData({
                    'user_name': response.user_data['nombre'],
                    'access_type': response.verification_type,
                    'confidence': response.confidence
                }))
```

---

## Summary

This API integration provides complete functionality for:

1. **Online facial verification** with automatic user identification
2. **Bidirectional data synchronization** for users and records
3. **Robust error handling** with automatic fallback mechanisms
4. **Comprehensive monitoring** of connectivity and system health
5. **Flexible configuration** for different deployment scenarios

The implementation follows best practices for:
- **Async/await patterns** for non-blocking operations
- **Retry logic** with exponential backoff for reliability
- **Local-first data strategy** for offline capability
- **Comprehensive logging** for debugging and monitoring
- **Type safety** with dataclasses and type hints

This documentation enables complete future development of the terminal firmware without requiring access to the API codebase.