"""
Main screen UI for the biometric terminal.
Displays camera preview, user instructions, and handles primary user interactions.
"""

import pygame
import numpy as np
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio
import threading
from pathlib import Path

from .base_ui import (UIScreen, UIComponent, UIButton, UILabel, UIImage, UIProgressBar,
                      UIRect, UIColors, UIFonts, create_centered_rect, create_grid_rect)
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData


class CameraPreviewComponent(UIComponent):
    """Component for displaying camera preview"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.camera_surface = None
        self.no_camera_text = "Cámara no disponible"
        self.face_detection_enabled = False
        self.face_boxes = []  # List of face detection boxes
        
    def set_camera_frame(self, frame: np.ndarray) -> None:
        """Set camera frame from numpy array"""
        if frame is None:
            self.camera_surface = None
            return
        
        # Convert numpy array to pygame surface
        # Assuming frame is in RGB format
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            # Resize frame to fit component
            import cv2
            frame = cv2.resize(frame, (self.rect.width, self.rect.height))
            
            # Convert to pygame surface
            frame_surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            self.camera_surface = frame_surface
        else:
            self.camera_surface = None
    
    def set_face_detections(self, face_boxes: list) -> None:
        """Set face detection boxes"""
        self.face_boxes = face_boxes or []
        self.face_detection_enabled = True
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw camera preview or placeholder
        if self.camera_surface:
            surface.blit(self.camera_surface, (self.rect.x, self.rect.y))
        else:
            # Draw placeholder
            pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect())
            
            # Draw "no camera" text
            font = pygame.font.Font(None, UIFonts.BODY)
            text_surface = font.render(self.no_camera_text, True, UIColors.TEXT_SECONDARY)
            text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
            surface.blit(text_surface, text_rect)
        
        # Draw face detection boxes
        if self.face_detection_enabled and self.face_boxes:
            for box in self.face_boxes:
                # box format: (x, y, width, height)
                x, y, w, h = box
                # Scale to component size
                scaled_x = self.rect.x + int(x * self.rect.width)
                scaled_y = self.rect.y + int(y * self.rect.height)
                scaled_w = int(w * self.rect.width)
                scaled_h = int(h * self.rect.height)
                
                # Draw green box for face detection
                pygame.draw.rect(surface, UIColors.SUCCESS, 
                               (scaled_x, scaled_y, scaled_w, scaled_h), 3)
                
                # Draw corner indicators
                corner_size = 20
                pygame.draw.lines(surface, UIColors.SUCCESS, False, [
                    (scaled_x, scaled_y + corner_size),
                    (scaled_x, scaled_y),
                    (scaled_x + corner_size, scaled_y)
                ], 3)
                
                pygame.draw.lines(surface, UIColors.SUCCESS, False, [
                    (scaled_x + scaled_w - corner_size, scaled_y),
                    (scaled_x + scaled_w, scaled_y),
                    (scaled_x + scaled_w, scaled_y + corner_size)
                ], 3)
                
                pygame.draw.lines(surface, UIColors.SUCCESS, False, [
                    (scaled_x + scaled_w, scaled_y + scaled_h - corner_size),
                    (scaled_x + scaled_w, scaled_y + scaled_h),
                    (scaled_x + scaled_w - corner_size, scaled_y + scaled_h)
                ], 3)
                
                pygame.draw.lines(surface, UIColors.SUCCESS, False, [
                    (scaled_x + corner_size, scaled_y + scaled_h),
                    (scaled_x, scaled_y + scaled_h),
                    (scaled_x, scaled_y + scaled_h - corner_size)
                ], 3)


class StatusIndicator(UIComponent):
    """Component for showing system status"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.status = "idle"
        self.message = "Acérquese al terminal"
        self.color = UIColors.TEXT_SECONDARY
        self.icon = None
        
    def set_status(self, status: str, message: str, color: tuple = UIColors.TEXT_SECONDARY) -> None:
        """Update status display"""
        self.status = status
        self.message = message
        self.color = color
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw status message
        font = pygame.font.Font(None, UIFonts.SUBTITLE)
        text_surface = font.render(self.message, True, self.color)
        text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
        surface.blit(text_surface, text_rect)
        
        # Draw status indicator dot
        dot_x = self.rect.x + 10
        dot_y = self.rect.center_y()
        pygame.draw.circle(surface, self.color, (dot_x, dot_y), 8)


class MainScreen(UIScreen):
    """Main screen for the biometric terminal"""
    
    def __init__(self):
        super().__init__("main")
        
        # Screen layout constants
        self.SCREEN_WIDTH = 400
        self.SCREEN_HEIGHT = 800
        self.HEADER_HEIGHT = 80
        self.FOOTER_HEIGHT = 120
        self.CAMERA_HEIGHT = 400
        
        # Components
        self.camera_preview = None
        self.status_indicator = None
        self.instruction_label = None
        self.time_label = None
        self.terminal_label = None
        self.manual_entry_button = None
        self.admin_button = None
        self.progress_bar = None
        
        # State
        self.current_instruction = "Acérquese al terminal"
        self.verification_progress = 0.0
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
        """Setup all UI components"""
        
        # Header section
        header_rect = UIRect(0, 0, self.SCREEN_WIDTH, self.HEADER_HEIGHT)
        
        # Terminal title
        self.terminal_label = UILabel(
            UIRect(20, 10, 280, 30),
            "BioEntry Terminal",
            UIFonts.TITLE,
            UIColors.PRIMARY,
            "left"
        )
        
        # Current time
        self.time_label = UILabel(
            UIRect(20, 45, 280, 25),
            self._get_current_time(),
            UIFonts.BODY,
            UIColors.TEXT_SECONDARY,
            "left"
        )
        
        # Admin button (top right)
        self.admin_button = UIButton(
            UIRect(320, 15, 60, 50),
            "Admin",
            self._on_admin_button_click,
            "outline"
        )
        
        # Camera preview section
        camera_y = self.HEADER_HEIGHT + 10
        self.camera_preview = CameraPreviewComponent(
            UIRect(20, camera_y, self.SCREEN_WIDTH - 40, self.CAMERA_HEIGHT)
        )
        
        # Status section
        status_y = camera_y + self.CAMERA_HEIGHT + 20
        self.status_indicator = StatusIndicator(
            UIRect(20, status_y, self.SCREEN_WIDTH - 40, 40)
        )
        
        # Instruction section
        instruction_y = status_y + 60
        self.instruction_label = UILabel(
            UIRect(20, instruction_y, self.SCREEN_WIDTH - 40, 80),
            self.current_instruction,
            UIFonts.BODY,
            UIColors.TEXT_PRIMARY,
            "center"
        )
        
        # Progress bar (initially hidden)
        progress_y = instruction_y + 100
        self.progress_bar = UIProgressBar(
            UIRect(50, progress_y, self.SCREEN_WIDTH - 100, 8)
        )
        self.progress_bar.set_visible(False)
        
        # Footer buttons
        footer_y = self.SCREEN_HEIGHT - self.FOOTER_HEIGHT + 20
        
        self.manual_entry_button = UIButton(
            UIRect(50, footer_y, self.SCREEN_WIDTH - 100, 50),
            "Ingreso Manual",
            self._on_manual_entry_button_click,
            "secondary"
        )
        
        # Add components to screen
        self.add_component(self.terminal_label)
        self.add_component(self.time_label)
        self.add_component(self.admin_button)
        self.add_component(self.camera_preview)
        self.add_component(self.status_indicator)
        self.add_component(self.instruction_label)
        self.add_component(self.progress_bar)
        self.add_component(self.manual_entry_button)
    
    def _get_current_time(self) -> str:
        """Get formatted current time"""
        now = datetime.now()
        return now.strftime("%H:%M:%S - %d/%m/%Y")
    
    def _on_admin_button_click(self) -> None:
        """Handle admin button click"""
        self.logger.info("Admin button clicked")
        # TODO: Show admin authentication screen
        # For now, just log the event
        
    def _on_manual_entry_button_click(self) -> None:
        """Handle manual entry button click"""
        self.logger.info("Manual entry button clicked")
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.MANUAL_ENTRY, "manual_button_click")
        )
    
    def _on_idle_state(self, state: SystemState, data: StateData) -> None:
        """Handle idle state"""
        self.status_indicator.set_status("idle", "Acérquese al terminal", UIColors.TEXT_SECONDARY)
        self.instruction_label.set_text("Acérquese al terminal para iniciar")
        self.progress_bar.set_visible(False)
        self.manual_entry_button.set_enabled(True)
        self.admin_button.set_enabled(True)
        
        # Disable face detection in idle
        self.camera_preview.face_detection_enabled = False
        
    def _on_activation_state(self, state: SystemState, data: StateData) -> None:
        """Handle activation state"""
        self.status_indicator.set_status("activating", "Activando...", UIColors.WARNING)
        self.instruction_label.set_text("Detectando usuario...")
        self.progress_bar.set_visible(True)
        self.progress_bar.set_value(0.1)
        self.manual_entry_button.set_enabled(False)
        
        # Enable face detection
        self.camera_preview.face_detection_enabled = True
    
    def _on_facial_recognition_state(self, state: SystemState, data: StateData) -> None:
        """Handle facial recognition state"""
        self.status_indicator.set_status("facial_recognition", "Reconocimiento facial", UIColors.PRIMARY)
        self.instruction_label.set_text("Mire hacia la cámara\nMantenga su rostro visible")
        self.progress_bar.set_visible(True)
        self.progress_bar.set_value(0.3)
        self.manual_entry_button.set_enabled(True)
        
        # Enable face detection
        self.camera_preview.face_detection_enabled = True
    
    def _on_fingerprint_verification_state(self, state: SystemState, data: StateData) -> None:
        """Handle fingerprint verification state"""
        self.status_indicator.set_status("fingerprint_verification", "Verificación de huella", UIColors.ACCENT)
        self.instruction_label.set_text("Coloque su dedo en el sensor\nde huellas dactilares")
        self.progress_bar.set_visible(True)
        self.progress_bar.set_value(0.6)
        self.manual_entry_button.set_enabled(True)
        
        # Disable face detection during fingerprint
        self.camera_preview.face_detection_enabled = False
    
    def _on_manual_entry_state(self, state: SystemState, data: StateData) -> None:
        """Handle manual entry state"""
        self.status_indicator.set_status("manual_entry", "Ingreso manual", UIColors.SECONDARY)
        self.instruction_label.set_text("Ingrese su número de documento")
        self.progress_bar.set_visible(False)
        self.manual_entry_button.set_enabled(False)
        
        # Disable face detection
        self.camera_preview.face_detection_enabled = False
    
    def _on_error_state(self, state: SystemState, data: StateData) -> None:
        """Handle error state"""
        error_message = "Error del sistema"
        if data and data.error_info:
            error_message = data.error_info.get("message", error_message)
        
        self.status_indicator.set_status("error", error_message, UIColors.ERROR)
        self.instruction_label.set_text("Se produjo un error\nIntente nuevamente")
        self.progress_bar.set_visible(False)
        self.manual_entry_button.set_enabled(True)
        self.admin_button.set_enabled(True)
        
        # Disable face detection
        self.camera_preview.face_detection_enabled = False
    
    def update(self) -> None:
        """Update screen state"""
        # Update time display
        self.time_label.set_text(self._get_current_time())
        
        # Update verification progress based on state
        current_state = self.state_manager.get_current_state()
        if current_state == SystemState.FACIAL_RECOGNITION:
            # Simulate progress during facial recognition
            duration = self.state_manager.get_state_duration()
            progress = min(0.8, 0.3 + (duration / 10) * 0.5)  # 30% to 80% over 10 seconds
            self.progress_bar.set_value(progress)
        
        elif current_state == SystemState.FINGERPRINT_VERIFICATION:
            # Simulate progress during fingerprint verification
            duration = self.state_manager.get_state_duration()
            progress = min(0.9, 0.6 + (duration / 5) * 0.3)  # 60% to 90% over 5 seconds
            self.progress_bar.set_value(progress)
    
    def set_camera_frame(self, frame: np.ndarray) -> None:
        """Update camera preview with new frame"""
        if self.camera_preview:
            self.camera_preview.set_camera_frame(frame)
    
    def set_face_detections(self, face_boxes: list) -> None:
        """Update face detection boxes"""
        if self.camera_preview:
            self.camera_preview.set_face_detections(face_boxes)
    
    def show_verification_feedback(self, success: bool, confidence: float = 0.0, 
                                 user_name: str = "") -> None:
        """Show verification feedback"""
        if success:
            self.status_indicator.set_status("success", f"Acceso concedido - {user_name}", UIColors.SUCCESS)
            self.instruction_label.set_text("Acceso concedido\nBienvenido")
            self.progress_bar.set_value(1.0)
        else:
            self.status_indicator.set_status("failed", "Verificación fallida", UIColors.ERROR)
            self.instruction_label.set_text("Verificación fallida\nIntente nuevamente")
            self.progress_bar.set_value(0.0)
    
    def show_connection_status(self, connected: bool) -> None:
        """Show connection status"""
        if not connected:
            # Show offline indicator
            self.status_indicator.set_status("offline", "Modo offline", UIColors.WARNING)
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the main screen"""
        # Draw header background
        header_rect = pygame.Rect(0, 0, self.SCREEN_WIDTH, self.HEADER_HEIGHT)
        pygame.draw.rect(surface, UIColors.SURFACE, header_rect)
        pygame.draw.line(surface, UIColors.BORDER, (0, self.HEADER_HEIGHT), 
                        (self.SCREEN_WIDTH, self.HEADER_HEIGHT), 2)
        
        # Draw footer background
        footer_rect = pygame.Rect(0, self.SCREEN_HEIGHT - self.FOOTER_HEIGHT, 
                                self.SCREEN_WIDTH, self.FOOTER_HEIGHT)
        pygame.draw.rect(surface, UIColors.SURFACE, footer_rect)
        pygame.draw.line(surface, UIColors.BORDER, (0, self.SCREEN_HEIGHT - self.FOOTER_HEIGHT), 
                        (self.SCREEN_WIDTH, self.SCREEN_HEIGHT - self.FOOTER_HEIGHT), 2)
        
        # Draw all components
        super().draw(surface)
        
        # Draw loading overlay if in certain states
        current_state = self.state_manager.get_current_state()
        if current_state in [SystemState.ACTIVATION, SystemState.FACIAL_RECOGNITION, 
                           SystemState.FINGERPRINT_VERIFICATION]:
            # Draw semi-transparent overlay
            overlay = pygame.Surface((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
            overlay.set_alpha(30)
            overlay.fill(UIColors.PRIMARY)
            surface.blit(overlay, (0, 0))


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