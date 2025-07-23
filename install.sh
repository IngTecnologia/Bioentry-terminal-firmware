#!/bin/bash

# BioEntry Terminal - Installation Script
# Sets up the development environment and installs dependencies

set -e  # Exit on any error

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect operating system
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            OS=$NAME
            VER=$VERSION_ID
        fi
        log_info "Detected OS: $OS $VER"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
        log_info "Detected OS: macOS"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        echo "Please install Python 3.8 or higher"
        exit 1
    fi
    
    # Check Python version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_info "Python version: $python_version"
    
    if ! python3 -c "import sys; assert sys.version_info >= (3, 8)" 2> /dev/null; then
        log_error "Python 3.8 or higher is required"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is required but not installed"
        exit 1
    fi
    
    log_success "System requirements met"
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."
    
    case "$OS" in
        *"Ubuntu"*|*"Debian"*)
            log_info "Installing dependencies for Debian/Ubuntu..."
            sudo apt-get update
            sudo apt-get install -y \
                python3-dev \
                python3-pip \
                python3-venv \
                build-essential \
                pkg-config \
                libsdl2-dev \
                libsdl2-image-dev \
                libsdl2-mixer-dev \
                libsdl2-ttf-dev \
                libportmidi-dev \
                libswscale-dev \
                libavformat-dev \
                libavcodec-dev \
                libfreetype6-dev \
                libopencv-dev \
                sqlite3 \
                curl
            ;;
        *"CentOS"*|*"Red Hat"*|*"Fedora"*)
            log_info "Installing dependencies for Red Hat/CentOS/Fedora..."
            sudo yum update -y
            sudo yum install -y \
                python3-devel \
                python3-pip \
                gcc \
                gcc-c++ \
                make \
                SDL2-devel \
                SDL2_image-devel \
                SDL2_mixer-devel \
                SDL2_ttf-devel \
                portmidi-devel \
                opencv-devel \
                sqlite \
                curl
            ;;
        *"Arch"*)
            log_info "Installing dependencies for Arch Linux..."
            sudo pacman -S --noconfirm \
                python \
                python-pip \
                base-devel \
                sdl2 \
                sdl2_image \
                sdl2_mixer \
                sdl2_ttf \
                portmidi \
                opencv \
                sqlite \
                curl
            ;;
        "macOS")
            log_info "Installing dependencies for macOS..."
            if command -v brew &> /dev/null; then
                brew install \
                    python3 \
                    sdl2 \
                    sdl2_image \
                    sdl2_mixer \
                    sdl2_ttf \
                    portmidi \
                    opencv \
                    sqlite3
            else
                log_warning "Homebrew not found. Please install Homebrew first:"
                echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                exit 1
            fi
            ;;
        *)
            log_warning "Unknown OS. You may need to install SDL2 and OpenCV manually."
            ;;
    esac
    
    log_success "System dependencies installed"
}

# Create virtual environment
create_venv() {
    log_info "Creating virtual environment..."
    
    if [[ -d "venv" ]]; then
        log_warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            log_info "Using existing virtual environment"
            return 0
        fi
    fi
    
    python3 -m venv venv
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    log_success "Virtual environment created"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Core dependencies
    pip install \
        pygame>=2.1.0 \
        opencv-python>=4.5.0 \
        numpy>=1.21.0 \
        requests>=2.25.0 \
        asyncio-mqtt>=0.10.0 \
        python-dotenv>=0.19.0
    
    # Development dependencies
    pip install \
        pytest>=6.0.0 \
        pytest-asyncio>=0.18.0 \
        black>=21.0.0 \
        flake8>=3.9.0 \
        mypy>=0.812
    
    # Hardware-specific dependencies (optional)
    log_info "Installing optional hardware dependencies..."
    
    # Try to install Raspberry Pi specific libraries
    pip install --no-deps --ignore-installed \
        RPi.GPIO \
        adafruit-circuitpython-apds9960 \
        pyfingerprint \
        picamera2 || {
        log_warning "Some hardware dependencies failed to install (normal on non-Raspberry Pi systems)"
    }
    
    # Generate requirements file
    pip freeze > requirements.txt
    
    log_success "Python dependencies installed"
}

# Set up directories and permissions
setup_directories() {
    log_info "Setting up directories..."
    
    # Create directory structure
    mkdir -p data/logs
    mkdir -p data/images
    mkdir -p data/backup
    mkdir -p docs
    mkdir -p tests
    
    # Set permissions
    chmod 755 data
    chmod 755 data/logs
    chmod 755 data/images
    chmod 755 data/backup
    
    # Make scripts executable
    chmod +x run.sh
    chmod +x install.sh
    
    log_success "Directories and permissions set up"
}

# Create initial configuration
create_config() {
    log_info "Creating initial configuration..."
    
    if [[ ! -f "data/config.json" ]]; then
        cat > data/config.json << 'EOF'
{
  "hardware": {
    "camera_enabled": true,
    "camera_resolution": [640, 480],
    "camera_fps": 15,
    "fingerprint_enabled": true,
    "proximity_enabled": true,
    "audio_enabled": true
  },
  "api": {
    "base_url": "http://localhost:8000",
    "terminal_id": "TERMINAL_001",
    "api_key": "terminal_key_001",
    "timeout": 30
  },
  "operation": {
    "mode": "hybrid",
    "location_name": "Terminal Principal"
  },
  "logging": {
    "level": "INFO",
    "file_path": "data/logs/terminal.log"
  }
}
EOF
        log_success "Default configuration created"
    else
        log_info "Configuration file already exists"
    fi
}

# Install systemd service (Linux only)
install_service() {
    if [[ "$OS" == *"Linux"* ]] && command -v systemctl &> /dev/null; then
        log_info "Installing systemd service..."
        
        read -p "Do you want to install systemd service for auto-start? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cat > /tmp/bioentry-terminal.service << EOF
[Unit]
Description=BioEntry Terminal Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=$SCRIPT_DIR/run.sh
Restart=always
RestartSec=10
Environment=MOCK_HARDWARE=false

[Install]
WantedBy=multi-user.target
EOF
            
            sudo mv /tmp/bioentry-terminal.service /etc/systemd/system/
            sudo systemctl daemon-reload
            sudo systemctl enable bioentry-terminal.service
            
            log_success "Systemd service installed"
            log_info "Use 'sudo systemctl start bioentry-terminal' to start"
            log_info "Use 'sudo systemctl status bioentry-terminal' to check status"
        fi
    fi
}

# Run tests
run_tests() {
    log_info "Running basic tests..."
    
    source venv/bin/activate
    
    # Test Python imports
    python3 -c "
import pygame
import cv2
import numpy
import requests
import sqlite3
print('All core modules imported successfully')
" || {
        log_error "Module import test failed"
        exit 1
    }
    
    # Test database creation
    python3 -c "
from core.database_manager import get_database_manager
import asyncio

async def test_db():
    db = get_database_manager()
    result = await db.initialize()
    print(f'Database test: {result}')
    await db.close()

asyncio.run(test_db())
" || {
        log_warning "Database test failed - check SQLite installation"
    }
    
    log_success "Basic tests completed"
}

# Show post-installation information
show_info() {
    echo
    echo "=================================================="
    echo "    BioEntry Terminal Installation Complete!"
    echo "=================================================="
    echo
    echo "Quick Start:"
    echo "  Development mode:  ./run.sh --dev"
    echo "  Mock hardware:     ./run.sh --mock"
    echo "  Production mode:   ./run.sh"
    echo
    echo "Configuration:"
    echo "  Config file:       data/config.json"
    echo "  Logs directory:    data/logs/"
    echo "  Database:          data/database.db"
    echo
    echo "Environment Variables:"
    echo "  TERMINAL_ID        Set terminal identifier"
    echo "  API_BASE_URL       Set API server URL"
    echo "  MOCK_HARDWARE=true Enable mock mode"
    echo
    echo "Documentation:"
    echo "  API Integration:   docs/API_INTEGRATION.md"
    echo "  Development:       CLAUDE.md"
    echo
    echo "Support:"
    echo "  Check logs in data/logs/ for troubleshooting"
    echo "  Run './run.sh --help' for usage information"
    echo
}

# Main installation function
main() {
    echo "=================================================="
    echo "    BioEntry Terminal - Installation Script"
    echo "=================================================="
    echo
    
    # Parse command line options
    SKIP_SYSTEM_DEPS=false
    DEV_MODE=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-system)
                SKIP_SYSTEM_DEPS=true
                shift
                ;;
            --dev)
                DEV_MODE=true
                shift
                ;;
            -h|--help)
                echo "Usage: $0 [OPTIONS]"
                echo
                echo "Options:"
                echo "  --skip-system    Skip system dependency installation"
                echo "  --dev           Install in development mode"
                echo "  -h, --help      Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run installation steps
    detect_os
    check_requirements
    
    if [[ "$SKIP_SYSTEM_DEPS" != "true" ]]; then
        install_system_deps
    else
        log_info "Skipping system dependencies installation"
    fi
    
    create_venv
    install_python_deps
    setup_directories
    create_config
    
    if [[ "$DEV_MODE" != "true" ]]; then
        install_service
    fi
    
    run_tests
    show_info
    
    log_success "Installation completed successfully!"
}

# Run main function
main "$@"