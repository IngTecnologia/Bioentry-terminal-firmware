#!/usr/bin/env python3
"""
BioEntry Terminal - Main Application
Complete biometric terminal firmware with hybrid online/offline capability.

This is the main entry point for the BioEntry terminal system.
It integrates all components and provides a complete access control solution.
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
import traceback

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Core system imports
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData

# Hardware managers
from core.camera_manager_simple import get_simple_camera_manager
from core.fingerprint_manager import FingerprintManager
from core.proximity_manager import ProximityManager
from core.database_manager import get_database_manager

# Services
from services.api_client import APIClient
from services.verification_service import get_verification_service, VerificationRequest
from services.sync_service import get_sync_service

# UI System
from ui.base_ui import UIManager
from ui.main_screen import MainScreen
from ui.success_screen import SuccessScreen
from ui.manual_entry_screen import ManualEntryScreen
from ui.admin_screen import AdminScreen

# Data models
from models.user import User
from models.access_record import AccessRecord


class BioEntryTerminal:
    """
    Main BioEntry Terminal application class.
    
    This class orchestrates all system components and provides the main
    application loop for the terminal firmware.
    """
    
    def __init__(self):
        # Initialize configuration and logging first
        self.config = get_config()
        self.logger = get_logger()
        
        # System managers
        self.state_manager = get_state_manager()
        self.db_manager = None  # Will be initialized in initialize() method
        
        # Hardware managers
        self.camera_manager = get_simple_camera_manager()
        self.fingerprint_manager = FingerprintManager()
        self.proximity_manager = ProximityManager()
        
        # Services
        self.api_client = APIClient()
        self.verification_service = get_verification_service()
        self.sync_service = get_sync_service()
        
        # UI System
        self.ui_manager = None
        self.current_screen = None
        
        # Application state
        self.running = False
        self.shutdown_event = asyncio.Event()
        
        # Performance tracking
        self.startup_time = None
        self.total_verifications = 0
        self.successful_verifications = 0
        
        self.logger.info("BioEntry Terminal initialized")
    
    async def _set_state(self, new_state: SystemState, data: Optional[StateData] = None, trigger: str = "system"):
        """Helper method to transition to a new state"""
        await self.state_manager.transition_to(new_state, trigger, data)
    
    async def initialize(self) -> bool:
        """
        Initialize all system components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Starting BioEntry Terminal initialization...")
            
            # Step 1: Initialize database
            self.logger.info("Initializing database...")
            try:
                self.db_manager = await get_database_manager()
                self.logger.info("Database initialization successful")
            except Exception as e:
                self.logger.error(f"Database initialization failed: {str(e)}")
                return False
            
            # Step 2: Initialize hardware managers
            self.logger.info("Initializing hardware managers...")
            
            # Simple camera manager (already initialized, just start it)
            try:
                self.camera_manager.start()
                self.logger.info("Simple camera manager started successfully")
            except Exception as e:
                self.logger.error(f"Camera initialization failed: {str(e)}")
                return False
            
            # Fingerprint manager
            if not await self.fingerprint_manager.initialize():
                self.logger.warning("Fingerprint sensor initialization failed - continuing without fingerprint support")
            
            # Proximity manager
            if not await self.proximity_manager.initialize():
                self.logger.warning("Proximity sensor initialization failed - manual activation only")
            
            # Step 3: Initialize UI system
            self.logger.info("Initializing UI system...")
            if not await self._initialize_ui():
                self.logger.error("UI initialization failed")
                return False
            
            # Step 4: Initialize services
            self.logger.info("Initializing services...")
            
            # Start sync service
            await self.sync_service.start_auto_sync()
            
            # Check API connectivity
            api_online = await self.api_client.check_connectivity()
            self.logger.info(f"API connectivity: {'Online' if api_online else 'Offline'}")
            
            # Step 5: Set up event handlers
            await self._setup_event_handlers()
            
            # Step 6: Set initial state (only if not already idle)
            current_state = self.state_manager.get_current_state()
            if current_state != SystemState.IDLE:
                await self._set_state(SystemState.IDLE, StateData(metadata={
                    'message': 'Terminal listo - Acerquese al sensor'
                }), "initialization")
            else:
                self.logger.info("System already in IDLE state, skipping transition")
            
            self.logger.info("BioEntry Terminal initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {str(e)}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _initialize_ui(self) -> bool:
        """Initialize the UI system and screens."""
        try:
            # Initialize UI manager
            self.ui_manager = UIManager()
            
            # Create screens
            main_screen = MainScreen()
            success_screen = SuccessScreen()
            manual_screen = ManualEntryScreen()
            admin_screen = AdminScreen()
            
            # Register screens
            self.logger.info(f"Registering main screen: {main_screen.name}")
            self.ui_manager.register_screen(main_screen)
            self.logger.info(f"Registering success screen: {success_screen.name}")
            self.ui_manager.register_screen(success_screen)
            self.logger.info(f"Registering manual screen: {manual_screen.name}")
            self.ui_manager.register_screen(manual_screen)
            self.logger.info(f"Registering admin screen: {admin_screen.name}")
            self.ui_manager.register_screen(admin_screen)
            
            # Debug: List all registered screens
            self.logger.info(f"All registered screens: {list(self.ui_manager.screens.keys())}")
            
            # Set initial screen
            self.ui_manager.show_screen('main')
            self.current_screen = 'main'
            
            return True
            
        except Exception as e:
            self.logger.error(f"UI initialization failed: {str(e)}")
            return False
    
    async def _setup_event_handlers(self):
        """Set up event handlers for system events."""
        # Proximity detection callback
        async def on_proximity_detected(detected: bool):
            if detected and self.state_manager.current_state == SystemState.IDLE:
                self.logger.info("User detected by proximity sensor")
                self.state_manager.set_state(SystemState.DETECTING, StateData({
                    'message': 'Usuario detectado - Preparando verificacion...'
                }))
        
        # Start proximity monitoring
        await self.proximity_manager.start_monitoring(
            lambda detected: asyncio.create_task(on_proximity_detected(detected))
        )
        
        # State change handler
        def on_state_change(transition_record: dict):
            new_state = transition_record.get('to_state')
            state_data = transition_record.get('data')
            self.logger.debug(f"State changed to: {new_state}")
            if new_state:
                asyncio.create_task(self._handle_state_change(new_state, state_data))
        
        self.state_manager.on_transition(on_state_change)
    
    async def _handle_state_change(self, new_state: SystemState, state_data: StateData):
        """Handle system state changes."""
        try:
            if new_state == SystemState.IDLE:
                # Return to main screen
                if self.current_screen != 'main':
                    self.ui_manager.show_screen('main')
                    self.current_screen = 'main'
            
            elif new_state == SystemState.DETECTING:
                # Start camera preview if not already started
                if not self.camera_manager.is_recording:
                    await self.camera_manager.start_preview()
            
            elif new_state == SystemState.VERIFYING:
                # Perform verification
                await self._perform_verification()
            
            elif new_state == SystemState.ACCESS_GRANTED:
                # Show success screen
                self.ui_manager.show_screen('success')
                self.current_screen = 'success'
                
                # Auto return to idle after delay
                await asyncio.sleep(self.config.operation.auto_return_delay)
                self.state_manager.set_state(SystemState.IDLE)
            
            elif new_state == SystemState.ACCESS_DENIED:
                # Show error and return to idle
                await asyncio.sleep(2)
                self.state_manager.set_state(SystemState.IDLE)
            
            elif new_state == SystemState.MANUAL_ENTRY:
                # Switch to manual entry screen
                self.ui_manager.show_screen('manual')
                self.current_screen = 'manual'
            
            elif new_state == SystemState.ADMIN_MODE:
                # Switch to admin screen
                self.ui_manager.show_screen('admin')
                self.current_screen = 'admin'
            
        except Exception as e:
            self.logger.error(f"Error handling state change: {str(e)}")
    
    async def _perform_verification(self):
        """Perform biometric verification based on system state."""
        try:
            self.total_verifications += 1
            
            # Capture image from camera
            image_data = self.camera_manager.capture_image()
            if not image_data:
                self.logger.error("Failed to capture image for verification")
                self.state_manager.set_state(SystemState.ACCESS_DENIED, StateData({
                    'error': 'Error de camara - Intente nuevamente'
                }))
                return
            
            # Create verification request
            request = VerificationRequest(
                method='facial',  # Primary method
                image_data=image_data,
                location=self._get_terminal_location()
            )
            
            # Perform verification with automatic fallback
            response = await self.verification_service.verify_with_fallback(request)
            
            if response.success and response.verified:
                # Verification successful
                self.successful_verifications += 1
                
                self.state_manager.set_state(SystemState.ACCESS_GRANTED, StateData({
                    'user_name': response.user_data.get('nombre', 'Usuario') if response.user_data else 'Usuario',
                    'access_type': response.verification_type,
                    'method': response.method_used,
                    'confidence': response.confidence,
                    'timestamp': response.timestamp
                }))
                
                self.logger.info(f"Verification successful: {response.user_data.get('nombre') if response.user_data else 'Unknown user'}")
                
            else:
                # Verification failed
                error_message = response.error_message or 'Verificacion fallida'
                
                self.state_manager.set_state(SystemState.ACCESS_DENIED, StateData({
                    'error': error_message,
                    'method_tried': response.method_used,
                    'fallback_available': response.fallback_available
                }))
                
                self.logger.warning(f"Verification failed: {error_message}")
                
        except Exception as e:
            self.logger.error(f"Verification error: {str(e)}")
            self.state_manager.set_state(SystemState.ACCESS_DENIED, StateData({
                'error': 'Error del sistema - Contacte al administrador'
            }))
    
    def _get_terminal_location(self) -> Optional[tuple]:
        """Get terminal location coordinates."""
        if (self.config.operation.location_lat and 
            self.config.operation.location_lng):
            return (self.config.operation.location_lat, 
                   self.config.operation.location_lng)
        return None
    
    async def run(self):
        """Main application loop."""
        try:
            self.running = True
            self.startup_time = asyncio.get_event_loop().time()
            
            self.logger.info("Starting BioEntry Terminal main loop")
            
            # Camera is already started during initialization
            
            # Import pygame for event handling
            import pygame
            
            # Main event loop with pygame integration
            while self.running:
                try:
                    # Process pygame events
                    events = pygame.event.get()
                    
                    for event in events:
                        
                        # Handle system events first
                        if event.type == pygame.QUIT:
                            self.running = False
                            break
                        elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                self.logger.info("Exit requested via ESC key")
                                self.running = False
                                break
                            else:
                                await self._handle_keyboard_event(event)
                        elif event.type == pygame.USEREVENT + 1:
                            # Handle custom UI events (like admin button)
                            if hasattr(event, 'action') and event.action == "show_screen":
                                screen_name = getattr(event, 'screen', None)
                                if screen_name and self.ui_manager:
                                    self.ui_manager.show_screen(screen_name)
                                    self.current_screen = screen_name
                        
                        # Pass ALL events to UI manager (including mouse events)
                        if self.ui_manager and self.ui_manager.current_screen:
                            self.ui_manager.current_screen.handle_event(event)
                    
                    # Update and draw UI if available
                    if self.ui_manager and self.ui_manager.current_screen:
                        # Get camera frame from simple camera manager
                        if self.camera_manager and self.camera_manager.is_running:
                            current_frame = self.camera_manager.get_current_frame()
                            if current_frame is not None:
                                # Update camera in main screen if it's active
                                if (hasattr(self.ui_manager.current_screen, 'fullscreen_camera') and 
                                    self.ui_manager.current_screen.fullscreen_camera):
                                    try:
                                        self.ui_manager.current_screen.fullscreen_camera.set_camera_frame(current_frame)
                                    except Exception as e:
                                        self.logger.error(f"Error setting camera frame: {str(e)}")
                            else:
                                # Log when we don't get frames
                                if hasattr(self.ui_manager.current_screen, 'fullscreen_camera'):
                                    if not hasattr(self, '_no_frame_logged'):
                                        self.logger.warning("No camera frame available from simple manager")
                                        self._no_frame_logged = True
                        
                        # Update current screen
                        self.ui_manager.current_screen.update()
                        
                        # Clear and draw
                        self.ui_manager.screen.fill((245, 245, 245))  # UIColors.BACKGROUND
                        self.ui_manager.current_screen.draw(self.ui_manager.screen)
                        
                        # Update display
                        pygame.display.flip()
                        self.ui_manager.clock.tick(30)
                    
                    # Background tasks
                    await self._check_manual_activation()
                    await self._periodic_maintenance()
                    
                    # Small delay
                    await asyncio.sleep(0.033)  # ~30 FPS
                    
                except KeyboardInterrupt:
                    self.logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    self.logger.error(f"Error in main loop: {str(e)}")
                    await asyncio.sleep(1)
            
        except Exception as e:
            self.logger.error(f"Critical error in main loop: {str(e)}")
            self.logger.error(traceback.format_exc())
        finally:
            await self.shutdown()
    
    async def _background_tasks(self):
        """Background tasks that run alongside the UI"""
        while self.running:
            try:
                # Check for manual activation (touch screen)
                await self._check_manual_activation()
                
                # Perform periodic maintenance
                await self._periodic_maintenance()
                
                # Small delay to prevent high CPU usage
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                self.logger.error(f"Error in background tasks: {str(e)}")
                await asyncio.sleep(1)
    
    async def _process_ui_events(self, events):
        """Process UI events from pygame."""
        for event in events:
            # Handle touch/click events
            if event.type == 'MOUSEBUTTONDOWN':
                # Manual activation via touch
                if self.state_manager.current_state == SystemState.IDLE:
                    self.state_manager.set_state(SystemState.DETECTING, StateData({
                        'message': 'Activacion manual - Preparando verificacion...',
                        'activation_method': 'touch'
                    }))
            
            # Handle keyboard events (for development)
            elif event.type == 'KEYDOWN':
                await self._handle_keyboard_event(event)
    
    async def _handle_keyboard_event(self, event):
        """Handle keyboard events for development and testing."""
        import pygame
        key = event.key
        
        if key == pygame.K_F1:  # Manual activation
            self.logger.info("F1 pressed - Manual activation")
        
        elif key == pygame.K_F2:  # Manual entry mode
            self.logger.info("F2 pressed - Manual entry mode")
            if self.ui_manager:
                self.ui_manager.show_screen("manual_entry")
        
        elif key == pygame.K_F3:  # Admin mode
            self.logger.info("F3 pressed - Admin mode")
            if self.ui_manager:
                self.ui_manager.show_screen("admin")
        
        elif key == pygame.K_F4:  # Simulate verification success
            self.logger.info("F4 pressed - Simulate success")
            if self.ui_manager:
                self.ui_manager.show_screen("success")
        
        elif key == pygame.K_F5:  # Return to main
            self.logger.info("F5 pressed - Return to main")
            if self.ui_manager:
                self.ui_manager.show_screen("main")
        
        elif key == pygame.K_ESCAPE:  # Exit application
            self.logger.info("Exit requested via ESC key")
            self.running = False
    
    async def _check_manual_activation(self):
        """Check for manual activation conditions."""
        # This would typically check for physical button press
        # or other manual activation methods
        pass
    
    async def _periodic_maintenance(self):
        """Perform periodic maintenance tasks."""
        current_time = asyncio.get_event_loop().time()
        
        # Check connectivity every 30 seconds
        if hasattr(self, '_last_connectivity_check'):
            if current_time - self._last_connectivity_check > 30:
                await self.api_client.check_connectivity()
                self._last_connectivity_check = current_time
        else:
            self._last_connectivity_check = current_time
        
        # Log status every 5 minutes
        if hasattr(self, '_last_status_log'):
            if current_time - self._last_status_log > 300:
                await self._log_system_status()
                self._last_status_log = current_time
        else:
            self._last_status_log = current_time
    
    async def _log_system_status(self):
        """Log current system status."""
        uptime = asyncio.get_event_loop().time() - (self.startup_time or 0)
        success_rate = (self.successful_verifications / max(self.total_verifications, 1)) * 100
        
        status = {
            'uptime_seconds': int(uptime),
            'total_verifications': self.total_verifications,
            'successful_verifications': self.successful_verifications,
            'success_rate': f"{success_rate:.1f}%",
            'current_state': self.state_manager.current_state.name,
            'api_online': self.api_client.is_online,
            'camera_recording': self.camera_manager.is_recording,
            'fingerprint_available': self.fingerprint_manager.is_available(),
            'proximity_monitoring': self.proximity_manager.is_monitoring
        }
        
        self.logger.info(f"System status: {status}")
    
    async def shutdown(self):
        """Graceful shutdown of the terminal."""
        try:
            self.logger.info("Starting graceful shutdown...")
            self.running = False
            
            # Stop services
            await self.sync_service.stop_auto_sync()
            
            # Stop hardware managers
            if self.camera_manager:
                self.camera_manager.stop()
            self.proximity_manager.stop_monitoring()
            
            # Cleanup hardware
            self.fingerprint_manager.cleanup()
            self.proximity_manager.cleanup()
            
            # Close database
            await self.db_manager.close()
            
            # Cleanup UI
            if self.ui_manager:
                self.ui_manager.cleanup()
            
            self.logger.info("Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {str(e)}")
    
    def signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        self.logger.info(f"Received signal {signum}")
        self.running = False
        self.shutdown_event.set()


async def main():
    """Main application entry point."""
    # Set up signal handlers
    terminal = BioEntryTerminal()
    
    def signal_handler(signum, frame):
        terminal.signal_handler(signum, frame)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize terminal
        if not await terminal.initialize():
            print("Terminal initialization failed")
            return 1
        
        # Run main application
        await terminal.run()
        
        return 0
        
    except Exception as e:
        print(f"Critical error: {str(e)}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # Check if running in mock mode
    if os.getenv("MOCK_HARDWARE"):
        print("Running in MOCK HARDWARE mode for development")
    
    # Run the terminal application
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nTerminal stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)