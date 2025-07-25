"""
Base UI framework for the biometric terminal.
Provides common UI components and utilities for all screens.
"""

import pygame
import sys
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import threading
import asyncio
from pathlib import Path

from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState


class UIColors:
    """Color constants for the UI - Professional Blue Theme"""
    PRIMARY = (25, 118, 210)       # Material Blue
    SECONDARY = (21, 101, 192)     # Darker Blue
    ACCENT = (33, 150, 243)        # Light Blue
    BACKGROUND = (248, 249, 250)   # Very Light Gray
    SURFACE = (255, 255, 255)      # White
    ERROR = (244, 67, 54)          # Red
    WARNING = (255, 152, 0)        # Orange
    SUCCESS = (76, 175, 80)        # Green (keep for success states)
    TEXT_PRIMARY = (33, 33, 33)    # Dark Gray
    TEXT_SECONDARY = (117, 117, 117) # Gray
    TEXT_DISABLED = (158, 158, 158) # Light Gray
    BORDER = (224, 224, 224)       # Light Border
    SHADOW = (0, 0, 0, 50)         # Semi-transparent black
    
    # Additional colors for modern design
    CARD_BACKGROUND = (255, 255, 255)  # White cards
    CARD_SHADOW = (0, 0, 0, 20)        # Light shadow
    HOVER = (227, 242, 253)            # Light blue hover


class UIFonts:
    """Font constants for the UI - Optimized for 4" touchscreen"""
    TITLE = 48        # Much larger for terminal title
    SUBTITLE = 32     # Larger subtitles
    BODY = 24         # Larger body text
    CAPTION = 18      # Larger captions
    BUTTON = 28       # Larger button text
    LARGE_BUTTON = 36 # For main action buttons
    SMALL = 16        # For admin/detailed info


@dataclass
class UIRect:
    """Rectangle utility class"""
    x: int
    y: int
    width: int
    height: int
    
    def get_pygame_rect(self) -> pygame.Rect:
        """Get pygame.Rect from UIRect"""
        return pygame.Rect(self.x, self.y, self.width, self.height)
    
    def center_x(self) -> int:
        """Get center X coordinate"""
        return self.x + self.width // 2
    
    def center_y(self) -> int:
        """Get center Y coordinate"""
        return self.y + self.height // 2
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside rectangle"""
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)


class UIComponent:
    """Base class for all UI components"""
    
    def __init__(self, rect: UIRect, visible: bool = True):
        self.rect = rect
        self.visible = visible
        self.enabled = True
        self.focused = False
        self.hover = False
        
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the component (override in subclasses)"""
        pass
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event, return True if handled"""
        if not self.visible or not self.enabled:
            return False
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                x, y = event.pos
                if self.rect.contains_point(x, y):
                    return self.on_click(x, y)
        
        elif event.type == pygame.MOUSEMOTION:
            x, y = event.pos
            was_hover = self.hover
            self.hover = self.rect.contains_point(x, y)
            if was_hover != self.hover:
                self.on_hover_change(self.hover)
        
        return False
    
    def on_click(self, x: int, y: int) -> bool:
        """Handle click event (override in subclasses)"""
        return False
    
    def on_hover_change(self, hover: bool) -> None:
        """Handle hover state change"""
        pass
    
    def set_visible(self, visible: bool) -> None:
        """Set component visibility"""
        self.visible = visible
    
    def set_enabled(self, enabled: bool) -> None:
        """Set component enabled state"""
        self.enabled = enabled


class UIButton(UIComponent):
    """Button UI component"""
    
    def __init__(self, rect: UIRect, text: str, callback: Optional[Callable] = None,
                 style: str = "primary", icon: Optional[str] = None):
        super().__init__(rect)
        self.text = text
        self.callback = callback
        self.style = style
        self.icon = icon
        self.pressed = False
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Determine colors based on state
        if self.style == "primary":
            bg_color = UIColors.PRIMARY
            text_color = UIColors.SURFACE
        elif self.style == "secondary":
            bg_color = UIColors.SECONDARY
            text_color = UIColors.SURFACE
        elif self.style == "outline":
            bg_color = UIColors.SURFACE
            text_color = UIColors.PRIMARY
        else:
            bg_color = UIColors.SURFACE
            text_color = UIColors.TEXT_PRIMARY
        
        # Modern button effects
        border_radius = 12  # More rounded corners
        shadow_offset = 2
        
        # Adjust for states with better visual feedback
        if not self.enabled:
            bg_color = UIColors.TEXT_DISABLED
            text_color = UIColors.SURFACE
            shadow_offset = 0
        elif self.pressed:
            bg_color = tuple(max(0, c - 30) for c in bg_color)
            shadow_offset = 1
        elif self.hover:
            if self.style == "outline":
                bg_color = UIColors.HOVER
            else:
                bg_color = tuple(min(255, c + 30) for c in bg_color)
            shadow_offset = 3
        
        # Draw shadow for depth
        if shadow_offset > 0:
            shadow_rect = pygame.Rect(
                self.rect.x + shadow_offset, 
                self.rect.y + shadow_offset,
                self.rect.width, 
                self.rect.height
            )
            shadow_surface = pygame.Surface((self.rect.width, self.rect.height))
            shadow_surface.set_alpha(30)
            shadow_surface.fill((0, 0, 0))
            surface.blit(shadow_surface, (shadow_rect.x, shadow_rect.y))
        
        # Draw button background
        pygame.draw.rect(surface, bg_color, self.rect.get_pygame_rect(), border_radius=border_radius)
        
        # Draw border for outline style
        if self.style == "outline":
            pygame.draw.rect(surface, UIColors.PRIMARY, self.rect.get_pygame_rect(), 
                           width=3, border_radius=border_radius)
        
        # Draw text with appropriate font size
        font_size = UIFonts.LARGE_BUTTON if self.rect.width > 150 else UIFonts.BUTTON
        font = pygame.font.Font(None, font_size)
        text_surface = font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
        surface.blit(text_surface, text_rect)
    
    def on_click(self, x: int, y: int) -> bool:
        if self.callback:
            self.callback()
        return True


class UILabel(UIComponent):
    """Label UI component"""
    
    def __init__(self, rect: UIRect, text: str, font_size: int = UIFonts.BODY,
                 color: Tuple[int, int, int] = UIColors.TEXT_PRIMARY, 
                 align: str = "left"):
        super().__init__(rect)
        self.text = text
        self.font_size = font_size
        self.color = color
        self.align = align
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        font = pygame.font.Font(None, self.font_size)
        text_surface = font.render(self.text, True, self.color)
        
        if self.align == "center":
            text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
        elif self.align == "right":
            text_rect = text_surface.get_rect(right=self.rect.x + self.rect.width,
                                            centery=self.rect.center_y())
        else:  # left
            text_rect = text_surface.get_rect(left=self.rect.x, centery=self.rect.center_y())
        
        surface.blit(text_surface, text_rect)
    
    def set_text(self, text: str) -> None:
        """Update label text"""
        self.text = text


class UIImage(UIComponent):
    """Image UI component"""
    
    def __init__(self, rect: UIRect, image_path: Optional[str] = None,
                 image_surface: Optional[pygame.Surface] = None):
        super().__init__(rect)
        self.image_surface = image_surface
        if image_path:
            self.load_image(image_path)
    
    def load_image(self, image_path: str) -> None:
        """Load image from file"""
        try:
            self.image_surface = pygame.image.load(image_path)
            self.image_surface = pygame.transform.scale(
                self.image_surface, (self.rect.width, self.rect.height)
            )
        except pygame.error as e:
            print(f"Error loading image {image_path}: {e}")
            self.image_surface = None
    
    def set_image(self, image_surface: pygame.Surface) -> None:
        """Set image from pygame surface"""
        self.image_surface = pygame.transform.scale(
            image_surface, (self.rect.width, self.rect.height)
        )
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or not self.image_surface:
            return
        
        surface.blit(self.image_surface, (self.rect.x, self.rect.y))


class UIProgressBar(UIComponent):
    """Progress bar UI component"""
    
    def __init__(self, rect: UIRect, value: float = 0.0, max_value: float = 1.0):
        super().__init__(rect)
        self.value = value
        self.max_value = max_value
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw background
        pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect(), border_radius=4)
        
        # Draw progress
        progress = min(1.0, self.value / self.max_value)
        progress_width = int(self.rect.width * progress)
        
        if progress_width > 0:
            progress_rect = pygame.Rect(self.rect.x, self.rect.y, progress_width, self.rect.height)
            pygame.draw.rect(surface, UIColors.PRIMARY, progress_rect, border_radius=4)
    
    def set_value(self, value: float) -> None:
        """Update progress value"""
        self.value = value


class UIScreen:
    """Base class for all UI screens"""
    
    def __init__(self, name: str):
        self.name = name
        self.components: List[UIComponent] = []
        self.config = get_config()
        self.logger = get_logger()
        self.state_manager = get_state_manager()
        self.active = False
        
    def add_component(self, component: UIComponent) -> None:
        """Add a component to the screen"""
        self.components.append(component)
    
    def remove_component(self, component: UIComponent) -> None:
        """Remove a component from the screen"""
        if component in self.components:
            self.components.remove(component)
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw all components"""
        for component in self.components:
            component.draw(surface)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event"""
        # Debug logging for touch events
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.logger.info(f"Touch event detected: pos={event.pos}, button={event.button}, screen={self.name}")
        
        # First, let components handle the event (including buttons)
        for component in reversed(self.components):  # Top to bottom
            if component.handle_event(event):
                self.logger.info(f"Event handled by component: {type(component).__name__}")
                return True
        
        # If no component handled it, then handle touch screen activation for main screen
        if event.type == pygame.MOUSEBUTTONDOWN and self.name == "main":
            self.logger.info("Touch activation triggered - no component handled the event")
            self._handle_touch_activation()
            return True
        
        return False
    
    def _handle_touch_activation(self) -> None:
        """Handle touch screen activation to start recognition"""
        current_state = self.state_manager.get_current_state()
        if current_state == SystemState.IDLE:
            # Activate recognition mode on touch
            import asyncio
            asyncio.create_task(
                self.state_manager.transition_to(SystemState.ACTIVATION, "touch_activation")
            )
            self.logger.info("Touch activation triggered")
    
    def on_activate(self) -> None:
        """Called when screen becomes active"""
        self.active = True
        self.logger.info(f"Screen activated: {self.name}")
    
    def on_deactivate(self) -> None:
        """Called when screen becomes inactive"""
        self.active = False
        self.logger.info(f"Screen deactivated: {self.name}")
    
    def update(self) -> None:
        """Update screen state (called every frame)"""
        pass


class UIManager:
    """Main UI manager class"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.state_manager = get_state_manager()
        
        # Initialize pygame
        pygame.init()
        
        # Enable touch screen support explicitly
        import os
        # Force SDL to use the correct input driver for touchscreen
        if not os.getenv('SDL_MOUSEDRV'):
            os.environ['SDL_MOUSEDRV'] = 'TSLIB'
        
        # Debug: Check available input devices
        print(f"DEBUG: Pygame version: {pygame.version.ver}")
        print(f"DEBUG: SDL version: {pygame.version.SDL}")
        try:
            print(f"DEBUG: Display driver: {pygame.display.get_driver()}")
        except:
            print("DEBUG: Could not get display driver")
        
        # Check if mouse is initialized (it should be after pygame.init())
        print(f"DEBUG: Mouse initialized: {hasattr(pygame.mouse, 'get_pressed')}")
        
        # Get screen dimensions for fullscreen display
        info = pygame.display.Info()
        self.screen_width = info.current_w
        self.screen_height = info.current_h
        
        # Set fullscreen mode like terminal_app.py
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height), pygame.FULLSCREEN)
        pygame.display.set_caption("BioEntry Terminal")
        
        # Hide mouse cursor for touchscreen interface
        pygame.mouse.set_visible(False)
        
        # Debug: Print screen info
        print(f"DEBUG: Screen dimensions: {self.screen_width}x{self.screen_height}")
        print(f"DEBUG: Screen mode: {'FULLSCREEN' if pygame.FULLSCREEN else 'WINDOWED'}")
        
        # Try to enable touch events explicitly
        try:
            # Allow all event types first
            pygame.event.set_allowed(None)
            # Then specifically ensure mouse events are allowed
            pygame.event.set_allowed([pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.KEYDOWN, pygame.QUIT])
            print("DEBUG: Touch events explicitly enabled")
        except Exception as e:
            print(f"DEBUG: Could not configure touch events: {e}")
        
        # Test event polling
        test_events = pygame.event.get()
        print(f"DEBUG: Initial event queue had {len(test_events)} events")
        
        # Force event pump to ensure events are being processed
        pygame.event.pump()
        
        # Screen management
        self.screens: Dict[str, UIScreen] = {}
        self.current_screen: Optional[UIScreen] = None
        
        # Event handling
        self.running = True
        self.clock = pygame.time.Clock()
        
        # State callbacks
        self.state_manager.on_state_enter(SystemState.IDLE, self._on_idle_state)
        self.state_manager.on_state_enter(SystemState.ACTIVATION, self._on_activation_state)
        self.state_manager.on_state_enter(SystemState.CONFIRMATION, self._on_confirmation_state)
        self.state_manager.on_state_enter(SystemState.ERROR, self._on_error_state)
        
        self.logger.info("UI Manager initialized")
    
    def register_screen(self, screen: UIScreen) -> None:
        """Register a screen with the UI manager"""
        self.screens[screen.name] = screen
        self.logger.debug(f"Screen registered: {screen.name}")
    
    def show_screen(self, screen_name: str) -> None:
        """Show a specific screen"""
        if screen_name not in self.screens:
            self.logger.error(f"Screen not found: {screen_name}")
            return
        
        # Deactivate current screen
        if self.current_screen:
            self.current_screen.on_deactivate()
        
        # Activate new screen
        self.current_screen = self.screens[screen_name]
        self.current_screen.on_activate()
        
        self.logger.info(f"Screen changed to: {screen_name}")
    
    def get_screen(self, screen_name: str) -> Optional[UIScreen]:
        """Get screen by name"""
        return self.screens.get(screen_name)
    
    def run(self) -> None:
        """Main UI loop"""
        self.logger.info("Starting UI main loop")
        
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.logger.info("Exit requested via ESC key")
                        self.running = False
                        break
                
                # Let current screen handle event
                if self.current_screen:
                    self.current_screen.handle_event(event)
            
            # Update current screen
            if self.current_screen:
                self.current_screen.update()
            
            # Clear screen
            self.screen.fill(UIColors.BACKGROUND)
            
            # Draw current screen
            if self.current_screen:
                self.current_screen.draw(self.screen)
            
            # Update display
            pygame.display.flip()
            self.clock.tick(30)  # 30 FPS
        
        self.logger.info("UI main loop ended")
    
    def stop(self) -> None:
        """Stop the UI manager"""
        self.running = False
        pygame.quit()
        self.logger.info("UI Manager stopped")
    
    def cleanup(self) -> None:
        """Cleanup UI resources"""
        self.stop()
    
    def _on_idle_state(self, state: SystemState, data: Any) -> None:
        """Handle idle state"""
        self.show_screen("main")
    
    def _on_activation_state(self, state: SystemState, data: Any) -> None:
        """Handle activation state"""
        self.show_screen("main")
    
    def _on_confirmation_state(self, state: SystemState, data: Any) -> None:
        """Handle confirmation state"""
        self.show_screen("success")
    
    def _on_error_state(self, state: SystemState, data: Any) -> None:
        """Handle error state"""
        # Show error overlay or switch to error screen
        pass
    
    def draw_loading_spinner(self, surface: pygame.Surface, center: Tuple[int, int], 
                           radius: int = 20, color: Tuple[int, int, int] = UIColors.PRIMARY) -> None:
        """Draw a loading spinner"""
        import math
        
        angle = (pygame.time.get_ticks() / 5) % 360
        
        for i in range(8):
            dot_angle = angle + i * 45
            dot_x = center[0] + radius * math.cos(math.radians(dot_angle))
            dot_y = center[1] + radius * math.sin(math.radians(dot_angle))
            
            alpha = 255 - (i * 30)
            alpha = max(50, alpha)
            
            dot_color = (*color, alpha)
            pygame.draw.circle(surface, color, (int(dot_x), int(dot_y)), 4)
    
    def draw_modal_background(self, surface: pygame.Surface, alpha: int = 128) -> None:
        """Draw semi-transparent modal background"""
        overlay = pygame.Surface((self.screen_width, self.screen_height))
        overlay.set_alpha(alpha)
        overlay.fill((0, 0, 0))
        surface.blit(overlay, (0, 0))


# Global UI manager instance
_ui_manager = None


def get_ui_manager() -> UIManager:
    """Get the global UI manager instance"""
    global _ui_manager
    if _ui_manager is None:
        _ui_manager = UIManager()
    return _ui_manager


def create_centered_rect(width: int, height: int, 
                        screen_width: int = 480, screen_height: int = 800,
                        y_offset: int = 0) -> UIRect:
    """Create a centered rectangle"""
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2 + y_offset
    return UIRect(x, y, width, height)


def create_grid_rect(col: int, row: int, cols: int, rows: int,
                    margin: int = 10, screen_width: int = 480, screen_height: int = 800) -> UIRect:
    """Create a rectangle in a grid layout"""
    cell_width = (screen_width - margin * (cols + 1)) // cols
    cell_height = (screen_height - margin * (rows + 1)) // rows
    
    x = margin + col * (cell_width + margin)
    y = margin + row * (cell_height + margin)
    
    return UIRect(x, y, cell_width, cell_height)


class UIFullscreenCamera(UIComponent):
    """Fullscreen camera preview component with overlays"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.camera_surface = None
        self.no_camera_text = "Cámara no disponible"
        self.face_detection_enabled = False
        self.face_boxes = []  # List of face detection boxes
        
        # Smooth transition system for face detection
        self.face_box_alpha = {}  # Track alpha for each box
        self.face_box_last_seen = {}  # Track when each box was last seen
        self.fade_speed = 8  # Alpha change per frame
        self.max_alpha = 255
        self.detection_stability_threshold = 3  # Frames to consider detection stable
        
    def set_camera_frame(self, frame) -> None:
        """Set camera frame from numpy array or pygame surface"""
        if frame is None:
            self.camera_surface = None
            return
        
        # If it's a numpy array, convert to pygame surface
        if hasattr(frame, 'shape'):
            import cv2
            import numpy as np
            try:
                # Resize frame to fullscreen
                frame_resized = cv2.resize(frame, (self.rect.width, self.rect.height))
                
                # Convert BGR to RGB (same as terminal_app.py)
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                
                # Convert to pygame surface with correct axis order
                frame_surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                self.camera_surface = frame_surface
                
            except Exception as e:
                # Log error but don't crash
                print(f"Error converting camera frame: {e}")
                self.camera_surface = None
        else:
            # Already a pygame surface
            # Scale to fullscreen  
            self.camera_surface = pygame.transform.scale(frame, (self.rect.width, self.rect.height))
    
    def set_face_detections(self, face_boxes: list) -> None:
        """Set face detection boxes with smooth transitions"""
        import time
        current_time = time.time()
        
        # Update face boxes and track timing
        self.face_boxes = face_boxes or []
        self.face_detection_enabled = True
        
        # Create unique IDs for face boxes based on position
        current_face_ids = set()
        for i, box in enumerate(self.face_boxes):
            face_id = f"face_{int(box[0]*100)}_{int(box[1]*100)}"
            current_face_ids.add(face_id)
            
            # Initialize or update face tracking
            if face_id not in self.face_box_alpha:
                self.face_box_alpha[face_id] = 0
            self.face_box_last_seen[face_id] = current_time
        
        # Fade out faces that are no longer detected
        faces_to_remove = []
        for face_id in list(self.face_box_alpha.keys()):
            if face_id not in current_face_ids:
                # Check if face has been gone long enough to start fading
                if current_time - self.face_box_last_seen.get(face_id, 0) > 0.1:  # 100ms grace period
                    self.face_box_alpha[face_id] = max(0, self.face_box_alpha[face_id] - self.fade_speed)
                    if self.face_box_alpha[face_id] <= 0:
                        faces_to_remove.append(face_id)
        
        # Remove completely faded faces
        for face_id in faces_to_remove:
            del self.face_box_alpha[face_id]
            if face_id in self.face_box_last_seen:
                del self.face_box_last_seen[face_id]
        
        # Fade in current faces
        for face_id in current_face_ids:
            if face_id in self.face_box_alpha:
                self.face_box_alpha[face_id] = min(self.max_alpha, 
                                                  self.face_box_alpha[face_id] + self.fade_speed)
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw camera preview fullscreen or placeholder
        if self.camera_surface:
            surface.blit(self.camera_surface, (self.rect.x, self.rect.y))
        else:
            # Draw black background as placeholder
            pygame.draw.rect(surface, (0, 0, 0), self.rect.get_pygame_rect())
            
            # Draw "no camera" text
            font = pygame.font.Font(None, UIFonts.SUBTITLE)
            text_surface = font.render(self.no_camera_text, True, UIColors.TEXT_SECONDARY)
            text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
            surface.blit(text_surface, text_rect)
        
        # Draw face detection boxes with smooth transitions
        if self.face_detection_enabled and (self.face_boxes or self.face_box_alpha):
            # Draw current faces
            for i, box in enumerate(self.face_boxes):
                face_id = f"face_{int(box[0]*100)}_{int(box[1]*100)}"
                alpha = self.face_box_alpha.get(face_id, 0)
                
                if alpha > 10:  # Only draw if sufficiently visible
                    x, y, w, h = box
                    # Scale to fullscreen size
                    scaled_x = self.rect.x + int(x * self.rect.width)
                    scaled_y = self.rect.y + int(y * self.rect.height)
                    scaled_w = int(w * self.rect.width)
                    scaled_h = int(h * self.rect.height)
                    
                    # Create surface for alpha blending
                    face_surface = pygame.Surface((scaled_w + 6, scaled_h + 6))
                    face_surface.set_alpha(alpha)
                    face_surface.fill((0, 0, 0, 0))
                    
                    # Draw modern face detection box with gradient effect
                    color_intensity = int(alpha / 255.0 * 255)
                    detection_color = (33, 150, 243, color_intensity)  # Blue with alpha
                    
                    # Draw main detection rectangle
                    pygame.draw.rect(face_surface, detection_color[:3], 
                                   (3, 3, scaled_w, scaled_h), 4)
                    
                    # Draw modern corner indicators with rounded corners
                    corner_size = 30
                    corner_thickness = 6
                    corner_color = detection_color[:3]
                    
                    # Top-left corner
                    pygame.draw.line(face_surface, corner_color, 
                                   (3, 3 + corner_size), (3, 3), corner_thickness)
                    pygame.draw.line(face_surface, corner_color, 
                                   (3, 3), (3 + corner_size, 3), corner_thickness)
                    
                    # Top-right corner  
                    pygame.draw.line(face_surface, corner_color, 
                                   (scaled_w + 3 - corner_size, 3), (scaled_w + 3, 3), corner_thickness)
                    pygame.draw.line(face_surface, corner_color, 
                                   (scaled_w + 3, 3), (scaled_w + 3, 3 + corner_size), corner_thickness)
                    
                    # Bottom-left corner
                    pygame.draw.line(face_surface, corner_color, 
                                   (3, scaled_h + 3 - corner_size), (3, scaled_h + 3), corner_thickness)
                    pygame.draw.line(face_surface, corner_color, 
                                   (3, scaled_h + 3), (3 + corner_size, scaled_h + 3), corner_thickness)
                    
                    # Bottom-right corner
                    pygame.draw.line(face_surface, corner_color, 
                                   (scaled_w + 3 - corner_size, scaled_h + 3), (scaled_w + 3, scaled_h + 3), corner_thickness)
                    pygame.draw.line(face_surface, corner_color, 
                                   (scaled_w + 3, scaled_h + 3), (scaled_w + 3, scaled_h + 3 - corner_size), corner_thickness)
                    
                    # Blit the face detection surface
                    surface.blit(face_surface, (scaled_x - 3, scaled_y - 3))
                    
                    # Draw "ROSTRO DETECTADO" text with fade
                    if alpha > 150:  # Only show text when detection is stable
                        font = pygame.font.Font(None, UIFonts.BODY)
                        text = "ROSTRO DETECTADO"
                        text_surface = font.render(text, True, UIColors.PRIMARY)
                        
                        # Position text above the detection box
                        text_x = scaled_x + (scaled_w - text_surface.get_width()) // 2
                        text_y = scaled_y - 40 if scaled_y > 50 else scaled_y + scaled_h + 15
                        
                        # Draw modern text background with rounded corners
                        text_bg_rect = pygame.Rect(text_x - 15, text_y - 8, 
                                                  text_surface.get_width() + 30, text_surface.get_height() + 16)
                        
                        # Create text background surface for alpha
                        text_bg_surface = pygame.Surface((text_bg_rect.width, text_bg_rect.height))
                        text_bg_surface.set_alpha(min(200, alpha))
                        text_bg_surface.fill((255, 255, 255))
                        pygame.draw.rect(text_bg_surface, (255, 255, 255), 
                                       (0, 0, text_bg_rect.width, text_bg_rect.height), border_radius=8)
                        
                        surface.blit(text_bg_surface, (text_bg_rect.x, text_bg_rect.y))
                        
                        # Draw text with alpha
                        text_alpha_surface = pygame.Surface(text_surface.get_size())
                        text_alpha_surface.set_alpha(alpha)
                        text_alpha_surface.blit(text_surface, (0, 0))
                        surface.blit(text_alpha_surface, (text_x, text_y))


class UIOverlay(UIComponent):
    """Semi-transparent overlay component for fullscreen elements"""
    
    def __init__(self, rect: UIRect, background_color: tuple = (0, 0, 0), alpha: int = 120):
        super().__init__(rect)
        self.background_color = background_color
        self.alpha = alpha
        self.child_components: List[UIComponent] = []
        
    def add_component(self, component: UIComponent) -> None:
        """Add a child component to this overlay"""
        self.child_components.append(component)
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw semi-transparent background
        overlay_surface = pygame.Surface((self.rect.width, self.rect.height))
        overlay_surface.set_alpha(self.alpha)
        overlay_surface.fill(self.background_color)
        surface.blit(overlay_surface, (self.rect.x, self.rect.y))
        
        # Draw child components
        for component in self.child_components:
            component.draw(surface)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events for child components"""
        if not self.visible or not self.enabled:
            return False
        
        for component in reversed(self.child_components):
            if component.handle_event(event):
                return True
        return False


if __name__ == "__main__":
    # Test the UI framework
    ui_manager = get_ui_manager()
    
    # Create a simple test screen
    test_screen = UIScreen("test")
    
    # Add some test components
    title_label = UILabel(
        create_centered_rect(300, 40, y_offset=-200),
        "BioEntry Terminal",
        UIFonts.TITLE,
        UIColors.PRIMARY,
        "center"
    )
    
    test_button = UIButton(
        create_centered_rect(200, 50),
        "Test Button",
        lambda: print("Button clicked!")
    )
    
    test_screen.add_component(title_label)
    test_screen.add_component(test_button)
    
    # Register and show screen
    ui_manager.register_screen(test_screen)
    ui_manager.show_screen("test")
    
    # Run UI
    ui_manager.run()