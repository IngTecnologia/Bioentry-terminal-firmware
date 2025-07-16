# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a biometric terminal firmware project for a hybrid online/offline access control system. The project contains a comprehensive implementation with working core modules including:

**IMPLEMENTED MODULES:**
- ✅ **Configuration Management** (`utils/config.py`) - Complete dataclass-based config with environment variable support
- ✅ **Logging System** (`utils/logger.py`) - Specialized logging with context-aware, performance, and error loggers
- ✅ **Database Manager** (`core/database_manager.py`) - SQLite-based Local-First persistence with sync queue
- ✅ **State Manager** (`utils/state_manager.py`) - Finite state machine with 9 states and controlled transitions
- ✅ **Complete UI System** (`ui/`) - Full pygame-based interface with 4 screens and specialized components

**PARTIALLY IMPLEMENTED:**
- 🔄 **API Integration** - New terminal-specific endpoints added to main API
- 🔄 **Hardware Abstraction** - Framework ready, individual drivers pending

**PENDING IMPLEMENTATION:**
- ❌ Hardware drivers (camera, fingerprint, proximity sensors)
- ❌ Service layer (verification, enrollment, sync services)
- ❌ Main application integration

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

# Run UI demo (standalone demonstration)
python ui_demo.py
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

## Implemented UI System

### UI Architecture

The terminal includes a complete pygame-based UI system with the following components:

**Base Framework (`ui/base_ui.py`):**
- `UIManager`: Main UI coordinator with screen management
- `UIComponent`: Base class for all UI elements
- `UIButton`, `UILabel`, `UIImage`, `UIProgressBar`: Core UI widgets
- `UIScreen`: Base class for application screens
- Consistent color scheme and typography system

**Screen Implementations:**

1. **Main Screen (`ui/main_screen.py`):**
   - Real-time camera preview with face detection overlays
   - Status indicators for system state
   - Progress bars for verification processes
   - Manual entry and admin access buttons
   - Automatic state-based UI updates

2. **Success Screen (`ui/success_screen.py`):**
   - Animated success checkmark with smooth transitions
   - User welcome message with fade-in effects
   - Access information display (time, method, confidence)
   - Automatic return to main screen after 3 seconds

3. **Manual Entry Screen (`ui/manual_entry_screen.py`):**
   - Numeric keypad for document ID input
   - Input validation with real-time feedback
   - Error handling with attempt counter
   - Mock verification integration

4. **Admin Screen (`ui/admin_screen.py`):**
   - System information and statistics panels
   - Configuration management interface
   - Quick action buttons (sync, backup, restart)
   - Multi-section navigation (status, users, config, diagnostics)

**Key UI Features:**
- **State Integration**: UI automatically responds to state machine transitions
- **Mock Mode Support**: Complete functionality without hardware
- **Responsive Design**: Optimized for 400x800 touchscreen
- **Accessibility**: Clear visual feedback and intuitive navigation
- **Performance**: 30 FPS with efficient rendering

### UI Demo Usage

Run the interactive demo to see all UI components:

```bash
# Install UI dependencies
pip install -r ui_requirements.txt

# Run demo with mock hardware
export MOCK_HARDWARE=true
python ui_demo.py
```

**Demo Controls:**
- `ESC` - Exit demo
- `F1` - Manual activation
- `F2` - Manual entry mode  
- `F3` - Admin screen
- `F4` - Simulate verification success
- `F5` - Return to main screen

The demo includes automatic proximity simulation, mock camera feeds, and realistic verification workflows.

This architecture provides a solid foundation for a production-ready biometric terminal with robust offline capabilities and seamless online integration.