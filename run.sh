#!/bin/bash

# BioEntry Terminal - Run Script
# Starts the terminal application with proper environment setup

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

# Check if running as root (required for hardware access)
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        log_warning "Running as root - hardware access enabled"
    else
        log_info "Running as regular user - mock mode will be enabled"
        export MOCK_HARDWARE=true
    fi
}

# Set up environment variables
setup_environment() {
    log_info "Setting up environment..."
    
    # Default environment for development
    export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
    
    # Check for development mode
    if [[ "$1" == "--dev" ]] || [[ "$1" == "-d" ]]; then
        log_info "Development mode enabled"
        export MOCK_HARDWARE=true
        export DEBUG_MODE=true
        export LOG_LEVEL=DEBUG
    fi
    
    # Check for mock mode
    if [[ "$1" == "--mock" ]] || [[ "$1" == "-m" ]]; then
        log_info "Mock hardware mode enabled"
        export MOCK_HARDWARE=true
    fi
    
    # Set terminal ID if not provided
    if [[ -z "$TERMINAL_ID" ]]; then
        export TERMINAL_ID="TERMINAL_001"
    fi
    
    # Set API URL if not provided
    if [[ -z "$API_BASE_URL" ]]; then
        export API_BASE_URL="http://localhost:8000"
    fi
    
    log_success "Environment configured"
}

# Check Python dependencies
check_dependencies() {
    log_info "Checking Python dependencies..."
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is not installed"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [[ -f "venv/bin/activate" ]]; then
        log_info "Activating virtual environment..."
        source venv/bin/activate
    else
        log_warning "No virtual environment found - using system Python"
    fi
    
    # Check critical dependencies
    python3 -c "import pygame, asyncio, sqlite3" 2>/dev/null || {
        log_error "Missing critical dependencies. Run install.sh first."
        exit 1
    }
    
    log_success "Dependencies check passed"
}

# Create necessary directories
setup_directories() {
    log_info "Setting up directories..."
    
    mkdir -p data/logs
    mkdir -p data/images
    mkdir -p data/backup
    
    # Set permissions
    chmod 755 data
    chmod 755 data/logs
    chmod 755 data/images
    chmod 755 data/backup
    
    log_success "Directories created"
}

# Show system information
show_system_info() {
    log_info "System Information:"
    echo "  OS: $(uname -s) $(uname -r)"
    echo "  Python: $(python3 --version)"
    echo "  Terminal ID: ${TERMINAL_ID}"
    echo "  API URL: ${API_BASE_URL}"
    echo "  Mock Mode: ${MOCK_HARDWARE:-false}"
    echo "  Debug Mode: ${DEBUG_MODE:-false}"
    echo "  Working Directory: $(pwd)"
}

# Check if API is accessible
check_api_connectivity() {
    if [[ "${MOCK_HARDWARE}" != "true" ]]; then
        log_info "Checking API connectivity..."
        
        if command -v curl &> /dev/null; then
            if curl -s --connect-timeout 5 "${API_BASE_URL}/docs" > /dev/null; then
                log_success "API server is accessible"
            else
                log_warning "API server is not accessible - terminal will run in offline mode"
            fi
        else
            log_warning "curl not available - cannot check API connectivity"
        fi
    fi
}

# Start the terminal application
start_terminal() {
    log_info "Starting BioEntry Terminal..."
    
    # Check if pygame display is available
    if [[ -z "$DISPLAY" ]] && [[ "$MOCK_HARDWARE" != "true" ]]; then
        log_warning "No display detected - GUI may not work"
    fi
    
    # Start with proper error handling
    python3 main.py "$@" || {
        local exit_code=$?
        log_error "Terminal application exited with code $exit_code"
        return $exit_code
    }
}

# Show usage information
show_usage() {
    echo "BioEntry Terminal - Run Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -d, --dev       Run in development mode (mock hardware + debug logging)"
    echo "  -m, --mock      Run with mock hardware only"
    echo "  -h, --help      Show this help message"
    echo
    echo "Environment Variables:"
    echo "  TERMINAL_ID     Terminal identifier (default: TERMINAL_001)"
    echo "  API_BASE_URL    API server URL (default: http://localhost:8000)"
    echo "  API_KEY         API authentication key"
    echo "  MOCK_HARDWARE   Enable mock hardware mode (true/false)"
    echo "  DEBUG_MODE      Enable debug logging (true/false)"
    echo
    echo "Examples:"
    echo "  $0                    # Run in production mode"
    echo "  $0 --dev             # Run in development mode"
    echo "  $0 --mock            # Run with mock hardware"
    echo "  TERMINAL_ID=TERM_002 $0  # Run with custom terminal ID"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    # Kill any background processes
    jobs -p | xargs -r kill
    
    log_success "Cleanup completed"
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    echo "=================================================="
    echo "       BioEntry Terminal - Starting Up"
    echo "=================================================="
    echo
    
    # Parse command line arguments
    case "$1" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -d|--dev)
            setup_environment "--dev"
            ;;
        -m|--mock)
            setup_environment "--mock"
            ;;
        *)
            setup_environment "$1"
            ;;
    esac
    
    # Run startup sequence
    check_permissions
    check_dependencies
    setup_directories
    show_system_info
    check_api_connectivity
    
    echo
    echo "=================================================="
    
    # Start the application
    start_terminal "$@"
    
    local exit_code=$?
    
    echo
    echo "=================================================="
    echo "       BioEntry Terminal - Shutdown"
    echo "=================================================="
    
    return $exit_code
}

# Run main function with all arguments
main "$@"