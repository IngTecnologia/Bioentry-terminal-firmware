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
    """Color constants for the UI"""
    PRIMARY = (34, 139, 34)        # Forest Green
    SECONDARY = (46, 125, 50)      # Dark Green
    ACCENT = (76, 175, 80)         # Light Green
    BACKGROUND = (245, 245, 245)   # Light Gray
    SURFACE = (255, 255, 255)      # White
    ERROR = (244, 67, 54)          # Red
    WARNING = (255, 193, 7)        # Amber
    SUCCESS = (76, 175, 80)        # Green
    TEXT_PRIMARY = (33, 33, 33)    # Dark Gray
    TEXT_SECONDARY = (117, 117, 117) # Gray
    TEXT_DISABLED = (158, 158, 158) # Light Gray
    BORDER = (224, 224, 224)       # Light Border
    SHADOW = (0, 0, 0, 50)         # Semi-transparent black


class UIFonts:
    """Font constants for the UI"""
    TITLE = 32
    SUBTITLE = 24
    BODY = 18
    CAPTION = 14
    BUTTON = 20


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
        
        # Adjust for states
        if not self.enabled:
            bg_color = UIColors.TEXT_DISABLED
            text_color = UIColors.SURFACE
        elif self.pressed:
            bg_color = tuple(max(0, c - 20) for c in bg_color)
        elif self.hover:
            bg_color = tuple(min(255, c + 20) for c in bg_color)
        
        # Draw button background
        pygame.draw.rect(surface, bg_color, self.rect.get_pygame_rect(), border_radius=8)
        
        # Draw border for outline style
        if self.style == "outline":
            pygame.draw.rect(surface, UIColors.PRIMARY, self.rect.get_pygame_rect(), 
                           width=2, border_radius=8)
        
        # Draw text
        font = pygame.font.Font(None, UIFonts.BUTTON)
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
        for component in reversed(self.components):  # Top to bottom
            if component.handle_event(event):
                return True
        return False
    
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
        
        # Screen setup
        self.screen_width = 400
        self.screen_height = 800
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("BioEntry Terminal")
        
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
                        screen_width: int = 400, screen_height: int = 800,
                        y_offset: int = 0) -> UIRect:
    """Create a centered rectangle"""
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2 + y_offset
    return UIRect(x, y, width, height)


def create_grid_rect(col: int, row: int, cols: int, rows: int,
                    margin: int = 10, screen_width: int = 400, screen_height: int = 800) -> UIRect:
    """Create a rectangle in a grid layout"""
    cell_width = (screen_width - margin * (cols + 1)) // cols
    cell_height = (screen_height - margin * (rows + 1)) // rows
    
    x = margin + col * (cell_width + margin)
    y = margin + row * (cell_height + margin)
    
    return UIRect(x, y, cell_width, cell_height)


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