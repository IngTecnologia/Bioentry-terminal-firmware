"""
Main screen UI for the biometric terminal.
Displays fullscreen camera preview with overlayed UI elements, similar to terminal_app.py approach.
"""

import pygame
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from .base_ui import (UIScreen, UIComponent, UIButton, UILabel, UIImage, UIProgressBar,
                      UIRect, UIColors, UIFonts, create_centered_rect, create_grid_rect,
                      UIFullscreenCamera, UIOverlay)
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData


class MainScreen(UIScreen):
    """Main screen for the biometric terminal with fullscreen camera and overlays"""
    
    def __init__(self):
        super().__init__("main")
        
        # Screen layout constants for 480x800 vertical display
        self.SCREEN_WIDTH = 480
        self.SCREEN_HEIGHT = 800
        # Fullscreen camera with overlays
        self.OVERLAY_HEIGHT = 120
        
        # Components
        self.fullscreen_camera = None
        self.top_overlay = None
        self.bottom_overlay = None
        self.time_label = None
        self.terminal_label = None
        self.online_status = None
        self.instruction_label = None
        self.admin_button = None
        
        # State
        self.current_instruction = "COLÓQUESE FRENTE A LA CÁMARA"
        self.last_frame_time = datetime.now()
        
        # Setup UI
        self._setup_ui()
        
        # State callbacks
        self.state_manager.on_state_enter(SystemState.IDLE, self._on_idle_state)
        self.state_manager.on_state_enter(SystemState.ACTIVATION, self._on_activation_state)
        self.state_manager.on_state_enter(SystemState.FACIAL_RECOGNITION, self._on_facial_recognition_state)
        self.state_manager.on_state_enter(SystemState.FINGERPRINT_VERIFICATION, self._on_fingerprint_verification_state)
        self.state_manager.on_state_enter(SystemState.MANUAL_ENTRY, self._on_manual_entry_state)
        self.state_manager.on_state_enter(SystemState.ERROR, self._on_error_state)
        
        self.logger.info("Main screen initialized")
    
    def _setup_ui(self) -> None:
        """Setup all UI components with fullscreen camera and overlays"""
        
        # Fullscreen camera background
        self.fullscreen_camera = UIFullscreenCamera(
            UIRect(0, 0, self.SCREEN_WIDTH, self.SCREEN_HEIGHT)
        )
        
        # Top overlay with title and status
        self.top_overlay = UIOverlay(
            UIRect(0, 0, self.SCREEN_WIDTH, self.OVERLAY_HEIGHT),
            background_color=(0, 0, 0),
            alpha=120
        )
        
        # Terminal title
        self.terminal_label = UILabel(
            UIRect(20, 20, 300, 60),
            "TERMINAL\nDE ACCESO",
            UIFonts.SUBTITLE,  # Smaller than new TITLE size
            UIColors.SURFACE,  # White text for better contrast
            "left"
        )
        
        # Current time
        self.time_label = UILabel(
            UIRect(self.SCREEN_WIDTH//2 - 60, 90, 120, 40),
            self._get_current_time(),
            UIFonts.BODY,
            UIColors.SURFACE,
            "center"
        )
        
        # Online status (top right)
        self.online_status = UILabel(
            UIRect(self.SCREEN_WIDTH - 130, 20, 110, 30),
            "● OFFLINE",
            UIFonts.BODY,
            UIColors.ERROR,
            "center"
        )
        
        # Admin button (larger for touch, bottom right corner)
        self.admin_button = UIButton(
            UIRect(self.SCREEN_WIDTH - 80, self.SCREEN_HEIGHT - 80, 60, 60),
            "⚙",
            self._on_admin_button_click,
            "outline"
        )
        
        # Bottom overlay with instructions
        self.bottom_overlay = UIOverlay(
            UIRect(0, self.SCREEN_HEIGHT - self.OVERLAY_HEIGHT, self.SCREEN_WIDTH, self.OVERLAY_HEIGHT),
            background_color=(0, 0, 0),
            alpha=120
        )
        
        # Instruction message
        self.instruction_label = UILabel(
            UIRect(20, self.SCREEN_HEIGHT - 100, self.SCREEN_WIDTH - 40, 80),
            "COLÓQUESE FRENTE\nA LA CÁMARA",
            UIFonts.SUBTITLE,
            UIColors.PRIMARY,  # Use primary blue color
            "center"
        )
        
        # Add components to overlays
        self.top_overlay.add_component(self.terminal_label)
        self.top_overlay.add_component(self.time_label)
        self.top_overlay.add_component(self.online_status)
        
        self.bottom_overlay.add_component(self.instruction_label)
        
        # Add main components to screen
        self.add_component(self.fullscreen_camera)  # Background
        self.add_component(self.top_overlay)        # Top overlay
        self.add_component(self.bottom_overlay)      # Bottom overlay
        self.add_component(self.admin_button)        # Admin button (on top)
    
    def _get_current_time(self) -> str:
        """Get formatted current time"""
        now = datetime.now()
        return now.strftime("%H:%M\n%d/%m")
    
    def _on_admin_button_click(self) -> None:
        """Handle admin button click"""
        self.logger.info("Admin button clicked")
        # Create a custom event that main.py can handle to switch screens
        # This is safer than trying to access UI manager from here
        import pygame
        # Send a custom event with admin screen request
        admin_event = pygame.event.Event(pygame.USEREVENT + 1, {"action": "show_screen", "screen": "admin"})
        pygame.event.post(admin_event)
    
    
    def _on_idle_state(self, state: SystemState, data: StateData) -> None:
        """Handle idle state"""
        self.instruction_label.set_text("COLÓQUESE FRENTE\nA LA CÁMARA")
        self.instruction_label.color = UIColors.SUCCESS
        self.admin_button.set_enabled(True)
        
        # Disable face detection in idle
        self.fullscreen_camera.face_detection_enabled = False
        
    def _on_activation_state(self, state: SystemState, data: StateData) -> None:
        """Handle activation state"""
        self.instruction_label.set_text("DETECTANDO\nUSUARIO...")
        self.instruction_label.color = UIColors.WARNING
        
        # Enable face detection
        self.fullscreen_camera.face_detection_enabled = True
    
    def _on_facial_recognition_state(self, state: SystemState, data: StateData) -> None:
        """Handle facial recognition state"""
        self.instruction_label.set_text("MIRE HACIA LA CÁMARA\nMANTENGA SU ROSTRO VISIBLE")
        self.instruction_label.color = UIColors.PRIMARY
        
        # Enable face detection
        self.fullscreen_camera.face_detection_enabled = True
    
    def _on_fingerprint_verification_state(self, state: SystemState, data: StateData) -> None:
        """Handle fingerprint verification state"""
        self.instruction_label.set_text("COLOQUE SU DEDO EN EL SENSOR\nDE HUELLAS DACTILARES")
        self.instruction_label.color = UIColors.ACCENT
        
        # Disable face detection during fingerprint
        self.fullscreen_camera.face_detection_enabled = False
    
    def _on_manual_entry_state(self, state: SystemState, data: StateData) -> None:
        """Handle manual entry state"""
        self.instruction_label.set_text("INGRESE SU NÚMERO\nDE DOCUMENTO")
        self.instruction_label.color = UIColors.SECONDARY
        
        # Disable face detection
        self.fullscreen_camera.face_detection_enabled = False
    
    def _on_error_state(self, state: SystemState, data: StateData) -> None:
        """Handle error state"""
        error_message = "ERROR DEL SISTEMA"
        if data and data.error_info:
            error_message = data.error_info.get("message", error_message)
        
        self.instruction_label.set_text(f"{error_message}\nINTENTE NUEVAMENTE")
        self.instruction_label.color = UIColors.ERROR
        self.admin_button.set_enabled(True)
        
        # Disable face detection
        self.fullscreen_camera.face_detection_enabled = False
    
    def update(self) -> None:
        """Update screen state"""
        # Update time display
        self.time_label.set_text(self._get_current_time())
    
    def set_camera_frame(self, frame: np.ndarray) -> None:
        """Update camera preview with new frame"""
        if self.fullscreen_camera:
            self.fullscreen_camera.set_camera_frame(frame)
    
    def set_face_detections(self, face_boxes: list) -> None:
        """Update face detection boxes"""
        if self.fullscreen_camera:
            self.fullscreen_camera.set_face_detections(face_boxes)
    
    def show_verification_feedback(self, success: bool, confidence: float = 0.0, 
                                 user_name: str = "") -> None:
        """Show verification feedback"""
        if success:
            self.instruction_label.set_text(f"ACCESO CONCEDIDO\nBIENVENIDO {user_name}")
            self.instruction_label.color = UIColors.SUCCESS
        else:
            self.instruction_label.set_text("VERIFICACIÓN FALLIDA\nINTENTE NUEVAMENTE")
            self.instruction_label.color = UIColors.ERROR
    
    def show_connection_status(self, connected: bool) -> None:
        """Show connection status"""
        if connected:
            self.online_status.set_text("● ONLINE")
            self.online_status.color = UIColors.SUCCESS
        else:
            self.online_status.set_text("● OFFLINE")
            self.online_status.color = UIColors.ERROR
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the main screen with fullscreen camera and overlays"""
        # Draw all components (camera fullscreen + overlays)
        super().draw(surface)


# Mock camera integration for testing
class MockCameraManager:
    """Mock camera manager for testing"""
    
    def __init__(self):
        self.running = False
        self.frame_callback = None
        self.face_callback = None
        
    def start(self, frame_callback, face_callback=None):
        """Start mock camera"""
        self.running = True
        self.frame_callback = frame_callback
        self.face_callback = face_callback
        
        # Start mock frame generation
        import threading
        threading.Thread(target=self._generate_frames, daemon=True).start()
    
    def stop(self):
        """Stop mock camera"""
        self.running = False
    
    def _generate_frames(self):
        """Generate mock camera frames"""
        import time
        
        while self.running:
            # Generate a simple colored frame
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            if self.frame_callback:
                self.frame_callback(frame)
            
            # Sometimes generate face detections
            if self.face_callback and np.random.random() < 0.3:
                # Mock face detection
                face_boxes = [(0.2, 0.2, 0.3, 0.4)]  # Normalized coordinates
                self.face_callback(face_boxes)
            
            time.sleep(1/15)  # 15 FPS


if __name__ == "__main__":
    # Test the main screen
    from .base_ui import get_ui_manager
    
    ui_manager = get_ui_manager()
    
    # Create and register main screen
    main_screen = MainScreen()
    ui_manager.register_screen(main_screen)
    
    # Mock camera for testing
    if main_screen.config.is_mock_mode():
        mock_camera = MockCameraManager()
        mock_camera.start(
            frame_callback=main_screen.set_camera_frame,
            face_callback=main_screen.set_face_detections
        )
    
    # Show main screen
    ui_manager.show_screen("main")
    
    # Run UI
    try:
        ui_manager.run()
    finally:
        if 'mock_camera' in locals():
            mock_camera.stop()
        ui_manager.stop()