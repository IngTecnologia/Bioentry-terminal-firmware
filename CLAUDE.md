# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a biometric terminal firmware project for a hybrid online/offline access control system. The project currently contains a comprehensive architectural blueprint with detailed documentation in README.md, but **all implementation files are empty placeholders**. This is effectively a well-structured template for implementing a biometric terminal system.

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Run installation script (when implemented)
./install.sh

# Start the system (when implemented)
./run.sh

# Run main application
python main.py
```

### Development with Hardware Mocking
```bash
# Set environment variables for development without hardware
export MOCK_HARDWARE=true
export MOCK_CAMERA=true
export MOCK_FINGERPRINT=true
export MOCK_PROXIMITY=true
export DEBUG_MODE=true
```

## Architecture Overview

### Core System Design

The system follows a **hybrid online/offline architecture** with three operational modes:

1. **Online Mode**: Facial recognition via API when connected
2. **Offline Mode**: Fingerprint verification using local AS608 sensor
3. **Manual Fallback**: Numeric ID entry when biometrics fail

### Key Architectural Principles

- **Local-First Data Strategy**: All access records saved to SQLite immediately, then synced to server
- **State Machine**: Centralized state management via `StateManager` with defined transitions
- **Event-Driven Communication**: Components communicate through `EventManager` using Observer pattern
- **Hardware Abstraction**: Clean separation between hardware interfaces and business logic

### Directory Structure and Responsibilities

```
core/          # Business logic layer
├── camera_manager.py      # Facial detection + API image capture
├── fingerprint_manager.py # AS608 sensor communication
├── proximity_manager.py   # APDS-9930 automatic activation
├── database_manager.py    # SQLite operations (single source of truth)
├── audio_manager.py       # User feedback sounds
└── connectivity_monitor.py # Network health monitoring

services/      # High-level orchestration
├── enrollment_service.py  # Complete user registration workflow
├── verification_service.py # Orchestrates facial vs fingerprint verification
└── sync_service.py        # Background sync with retry logic

ui/           # User interface screens
├── main_screen.py         # Camera preview + real-time detection
├── admin_screen.py        # Configuration and user management
├── registration_screen.py # Fingerprint enrollment process
├── manual_entry_screen.py # Fallback numeric keypad
└── success_screen.py      # Access confirmation display

hardware/     # Hardware abstraction layer
├── camera_handler.py      # Picamera2 wrapper
├── i2c_handler.py         # I2C communication (APDS-9930)
└── uart_handler.py        # UART communication (AS608)

models/       # Data structures
├── user.py                # User entity with validations
├── access_record.py       # Access log entries
└── sync_queue.py          # Sync queue management

utils/        # Shared utilities
├── config.py              # Configuration management
├── logger.py              # Structured logging
├── state_manager.py       # Global state machine
└── crypto.py              # Cryptographic utilities
```

### Critical Data Flow

1. **User Detection**: `proximity_manager` → `state_manager` → mode selection
2. **Verification**: `verification_service` orchestrates facial/fingerprint verification
3. **Recording**: `database_manager` saves locally → `sync_service` queues for server
4. **Synchronization**: Background process with exponential backoff retry

### Hardware Integration

- **Raspberry Pi Zero 2W**: Main processing unit (resource-constrained)
- **OV5647 Camera**: Facial recognition (online mode)
- **AS608 Fingerprint Sensor**: Local verification (offline mode, stores 1-162 templates)
- **APDS-9930 Proximity Sensor**: Automatic activation via I2C
- **4" Touchscreen**: User interface (400x800 vertical)

### Database Schema (SQLite)

```sql
users: id, employee_id, document_id, name, fingerprint_template_id, is_active
access_records: user_id, timestamp, method, verification_type, confidence_score, is_synced
sync_queue: record_id, action, attempts, status, last_attempt
```

### Key Implementation Notes

- **Fingerprint Templates**: Stored in AS608 sensor (not in database), database maps template_id to user_id
- **Sync Strategy**: All data saved locally first, then synced to server when connectivity available
- **State Transitions**: Defined valid transitions prevent invalid system states
- **Error Handling**: Graceful fallback between verification methods
- **Performance**: Optimized for Pi Zero 2W constraints (15fps camera, detection every 3 frames)

### Testing Strategy

- **Mock Hardware**: Use environment variables to enable hardware mocking for development
- **Unit Tests**: Test individual managers and services in isolation
- **Integration Tests**: Test complete user flows with mocked hardware
- **Hardware Tests**: Run on actual device for final validation

### Development Workflow

1. **Start with Mock Hardware**: Set environment variables for hardware-free development
2. **Implement Core Managers**: Begin with `database_manager` and `state_manager`
3. **Add Hardware Abstraction**: Implement hardware handlers with mock alternatives
4. **Build Services Layer**: Create verification and sync services
5. **Develop UI Components**: Build screens with state machine integration
6. **Integration Testing**: Test complete workflows
7. **Hardware Integration**: Test on actual Raspberry Pi with sensors

This architecture provides a solid foundation for a production-ready biometric terminal with robust offline capabilities and seamless online integration.