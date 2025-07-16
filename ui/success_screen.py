"""
Success screen UI for the biometric terminal.
Displays confirmation when access is granted with user information.
"""

import pygame
import math
from typing import Optional, Dict, Any
from datetime import datetime
import asyncio

from .base_ui import (UIScreen, UIComponent, UIButton, UILabel, UIImage, UIRect, 
                      UIColors, UIFonts, create_centered_rect)
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData


class SuccessIcon(UIComponent):
    """Animated success checkmark icon"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.animation_progress = 0.0
        self.animation_speed = 0.05
        self.checkmark_drawn = False
        self.circle_drawn = False
        
    def update(self) -> None:
        """Update animation progress"""
        if self.animation_progress < 1.0:
            self.animation_progress += self.animation_speed
            if self.animation_progress >= 1.0:
                self.animation_progress = 1.0
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        center_x = self.rect.center_x()
        center_y = self.rect.center_y()
        radius = min(self.rect.width, self.rect.height) // 2 - 10
        
        # Draw circle background (animated)
        circle_progress = min(1.0, self.animation_progress * 2)
        if circle_progress > 0:
            # Draw circle with animation
            if circle_progress >= 1.0:
                pygame.draw.circle(surface, UIColors.SUCCESS, (center_x, center_y), radius)
                pygame.draw.circle(surface, UIColors.SURFACE, (center_x, center_y), radius, 3)
            else:
                # Partial circle animation
                import math
                angle = circle_progress * 2 * math.pi
                points = []
                for i in range(int(angle * 20)):
                    x = center_x + radius * math.cos(i * math.pi / 20)
                    y = center_y + radius * math.sin(i * math.pi / 20)
                    points.append((x, y))
                if len(points) > 1:
                    pygame.draw.lines(surface, UIColors.SUCCESS, False, points, 3)
        
        # Draw checkmark (animated)
        checkmark_progress = max(0.0, min(1.0, (self.animation_progress - 0.3) * 2))
        if checkmark_progress > 0:
            # Checkmark points
            check_size = radius * 0.6
            check_start_x = center_x - check_size * 0.3
            check_start_y = center_y + check_size * 0.1
            check_mid_x = center_x - check_size * 0.1
            check_mid_y = center_y + check_size * 0.3
            check_end_x = center_x + check_size * 0.4
            check_end_y = center_y - check_size * 0.2
            
            # Draw first line of checkmark
            line1_progress = min(1.0, checkmark_progress * 2)
            if line1_progress > 0:
                line1_end_x = check_start_x + (check_mid_x - check_start_x) * line1_progress
                line1_end_y = check_start_y + (check_mid_y - check_start_y) * line1_progress
                pygame.draw.line(surface, UIColors.SURFACE, 
                               (check_start_x, check_start_y), (line1_end_x, line1_end_y), 8)
            
            # Draw second line of checkmark
            line2_progress = max(0.0, min(1.0, (checkmark_progress - 0.5) * 2))
            if line2_progress > 0 and line1_progress >= 1.0:
                line2_end_x = check_mid_x + (check_end_x - check_mid_x) * line2_progress
                line2_end_y = check_mid_y + (check_end_y - check_mid_y) * line2_progress
                pygame.draw.line(surface, UIColors.SURFACE, 
                               (check_mid_x, check_mid_y), (line2_end_x, line2_end_y), 8)
    
    def reset_animation(self) -> None:
        """Reset animation to beginning"""
        self.animation_progress = 0.0
        self.checkmark_drawn = False
        self.circle_drawn = False


class WelcomeMessage(UIComponent):
    """Animated welcome message"""
    
    def __init__(self, rect: UIRect, user_name: str = ""):
        super().__init__(rect)
        self.user_name = user_name
        self.animation_progress = 0.0
        self.animation_speed = 0.02
        self.fade_in_complete = False
        
    def set_user_name(self, user_name: str) -> None:
        """Set the user name to display"""
        self.user_name = user_name
        self.animation_progress = 0.0
        self.fade_in_complete = False
        
    def update(self) -> None:
        """Update animation progress"""
        if self.animation_progress < 1.0:
            self.animation_progress += self.animation_speed
            if self.animation_progress >= 1.0:
                self.animation_progress = 1.0
                self.fade_in_complete = True
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Calculate alpha based on animation progress
        alpha = int(255 * min(1.0, self.animation_progress))
        
        # Welcome text
        welcome_text = "¡Bienvenido!"
        font_welcome = pygame.font.Font(None, UIFonts.TITLE)
        welcome_surface = font_welcome.render(welcome_text, True, UIColors.SUCCESS)
        welcome_surface.set_alpha(alpha)
        
        # User name text
        user_text = self.user_name if self.user_name else "Usuario"
        font_user = pygame.font.Font(None, UIFonts.SUBTITLE)
        user_surface = font_user.render(user_text, True, UIColors.TEXT_PRIMARY)
        user_surface.set_alpha(alpha)
        
        # Position texts
        welcome_rect = welcome_surface.get_rect(center=(self.rect.center_x(), self.rect.y + 30))
        user_rect = user_surface.get_rect(center=(self.rect.center_x(), self.rect.y + 70))
        
        # Draw texts
        surface.blit(welcome_surface, welcome_rect)
        surface.blit(user_surface, user_rect)
    
    def reset_animation(self) -> None:
        """Reset animation to beginning"""
        self.animation_progress = 0.0
        self.fade_in_complete = False


class AccessInfo(UIComponent):
    """Component to display access information"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.access_time = datetime.now()
        self.verification_method = "facial"
        self.confidence_score = 0.0
        self.location = "Terminal Principal"
        
    def set_access_info(self, access_time: datetime, method: str, confidence: float, location: str) -> None:
        """Set access information"""
        self.access_time = access_time
        self.verification_method = method
        self.confidence_score = confidence
        self.location = location
        
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Format access time
        time_str = self.access_time.strftime("%H:%M:%S")
        date_str = self.access_time.strftime("%d/%m/%Y")
        
        # Method display
        method_display = {
            "facial": "Reconocimiento Facial",
            "fingerprint": "Huella Dactilar",
            "manual": "Ingreso Manual"
        }.get(self.verification_method, "Desconocido")
        
        # Confidence display
        confidence_str = f"{self.confidence_score:.1%}" if self.confidence_score > 0 else "N/A"
        
        # Create info lines
        info_lines = [
            f"Hora: {time_str}",
            f"Fecha: {date_str}",
            f"Método: {method_display}",
            f"Confianza: {confidence_str}",
            f"Ubicación: {self.location}"
        ]
        
        # Draw info lines
        font = pygame.font.Font(None, UIFonts.BODY)
        y_offset = 0
        line_height = 30
        
        for line in info_lines:
            text_surface = font.render(line, True, UIColors.TEXT_SECONDARY)
            text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.y + y_offset + 15))
            surface.blit(text_surface, text_rect)
            y_offset += line_height


class SuccessScreen(UIScreen):
    """Success screen for displaying access granted confirmation"""
    
    def __init__(self):
        super().__init__("success")
        
        # Screen layout constants
        self.SCREEN_WIDTH = 400
        self.SCREEN_HEIGHT = 800
        self.AUTO_RETURN_DELAY = 3.0  # seconds
        
        # Components
        self.success_icon = None
        self.welcome_message = None
        self.access_info = None
        self.return_button = None
        self.countdown_label = None
        
        # State
        self.show_start_time = None
        self.user_name = ""
        self.access_time = datetime.now()
        self.verification_method = "facial"
        self.confidence_score = 0.0
        self.location = "Terminal Principal"
        
        # Setup UI
        self._setup_ui()
        
        # State callbacks
        self.state_manager.on_state_enter(SystemState.CONFIRMATION, self._on_confirmation_state)
        
        self.logger.info("Success screen initialized")
    
    def _setup_ui(self) -> None:
        """Setup all UI components"""
        
        # Success icon (animated checkmark)
        self.success_icon = SuccessIcon(
            create_centered_rect(120, 120, y_offset=-200)
        )
        
        # Welcome message
        self.welcome_message = WelcomeMessage(
            create_centered_rect(350, 100, y_offset=-50),
            self.user_name
        )
        
        # Access information
        self.access_info = AccessInfo(
            create_centered_rect(350, 150, y_offset=80)
        )
        
        # Return button
        self.return_button = UIButton(
            create_centered_rect(200, 50, y_offset=250),
            "Continuar",
            self._on_return_button_click,
            "primary"
        )
        
        # Countdown label
        self.countdown_label = UILabel(
            create_centered_rect(350, 30, y_offset=320),
            "Regresando automáticamente en 3s",
            UIFonts.CAPTION,
            UIColors.TEXT_SECONDARY,
            "center"
        )
        
        # Add components to screen
        self.add_component(self.success_icon)
        self.add_component(self.welcome_message)
        self.add_component(self.access_info)
        self.add_component(self.return_button)
        self.add_component(self.countdown_label)
    
    def _on_confirmation_state(self, state: SystemState, data: StateData) -> None:
        """Handle confirmation state entry"""
        self.show_start_time = datetime.now()
        
        # Extract user data from state
        if data and data.user_data:
            self.user_name = data.user_data.get("name", "Usuario")
            self.access_time = datetime.now()
            
        if data and data.verification_result:
            self.verification_method = data.verification_result.get("method", "facial")
            self.confidence_score = data.verification_result.get("confidence", 0.0)
            
        # Get location from config
        self.location = self.config.operation.location_name
        
        # Update components
        self.welcome_message.set_user_name(self.user_name)
        self.access_info.set_access_info(self.access_time, self.verification_method, 
                                       self.confidence_score, self.location)
        
        # Reset animations
        self.success_icon.reset_animation()
        self.welcome_message.reset_animation()
        
        self.logger.info("Success screen activated", user_name=self.user_name)
    
    def _on_return_button_click(self) -> None:
        """Handle return button click"""
        self.logger.info("Return button clicked")
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.IDLE, "return_button_click")
        )
    
    def update(self) -> None:
        """Update screen state"""
        if not self.active or not self.show_start_time:
            return
        
        # Update animations
        self.success_icon.update()
        self.welcome_message.update()
        
        # Update countdown
        elapsed = (datetime.now() - self.show_start_time).total_seconds()
        remaining = max(0, self.AUTO_RETURN_DELAY - elapsed)
        
        if remaining > 0:
            self.countdown_label.set_text(f"Regresando automáticamente en {remaining:.0f}s")
            self.countdown_label.set_visible(True)
        else:
            self.countdown_label.set_visible(False)
            # Auto return to idle
            if self.state_manager.get_current_state() == SystemState.CONFIRMATION:
                asyncio.create_task(
                    self.state_manager.transition_to(SystemState.IDLE, "auto_return")
                )
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the success screen"""
        # Draw background with subtle pattern
        surface.fill(UIColors.BACKGROUND)
        
        # Draw success background effect
        if self.success_icon.animation_progress > 0.5:
            # Subtle radial gradient effect
            center_x = self.SCREEN_WIDTH // 2
            center_y = self.SCREEN_HEIGHT // 2
            
            # Draw concentric circles for effect
            for i in range(3):
                alpha = int(30 * (1 - i * 0.3) * self.success_icon.animation_progress)
                radius = 100 + i * 50
                
                # Create surface for circle with alpha
                circle_surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(circle_surface, (*UIColors.SUCCESS, alpha), 
                                 (radius, radius), radius)
                
                surface.blit(circle_surface, (center_x - radius, center_y - radius))
        
        # Draw all components
        super().draw(surface)
        
        # Draw additional decorative elements
        self._draw_decorative_elements(surface)
    
    def _draw_decorative_elements(self, surface: pygame.Surface) -> None:
        """Draw decorative elements"""
        if self.success_icon.animation_progress < 0.8:
            return
        
        # Draw small dots around the success icon
        center_x = self.success_icon.rect.center_x()
        center_y = self.success_icon.rect.center_y()
        
        import math
        for i in range(8):
            angle = i * math.pi / 4
            distance = 80
            dot_x = center_x + distance * math.cos(angle)
            dot_y = center_y + distance * math.sin(angle)
            
            # Animate dots appearance
            dot_alpha = int(255 * max(0, min(1, (self.success_icon.animation_progress - 0.8) * 5)))
            
            if dot_alpha > 0:
                dot_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
                pygame.draw.circle(dot_surface, (*UIColors.SUCCESS, dot_alpha), (4, 4), 4)
                surface.blit(dot_surface, (dot_x - 4, dot_y - 4))
    
    def set_user_data(self, user_data: Dict[str, Any]) -> None:
        """Set user data for display"""
        self.user_name = user_data.get("name", "Usuario")
        self.welcome_message.set_user_name(self.user_name)
        
    def set_verification_result(self, method: str, confidence: float) -> None:
        """Set verification result data"""
        self.verification_method = method
        self.confidence_score = confidence
        self.access_time = datetime.now()
        
        self.access_info.set_access_info(self.access_time, method, confidence, self.location)
    
    def on_activate(self) -> None:
        """Called when screen becomes active"""
        super().on_activate()
        self.show_start_time = datetime.now()
        
        # Reset animations
        self.success_icon.reset_animation()
        self.welcome_message.reset_animation()
    
    def on_deactivate(self) -> None:
        """Called when screen becomes inactive"""
        super().on_deactivate()
        self.show_start_time = None


if __name__ == "__main__":
    # Test the success screen
    from .base_ui import get_ui_manager
    import time
    
    ui_manager = get_ui_manager()
    
    # Create and register success screen
    success_screen = SuccessScreen()
    ui_manager.register_screen(success_screen)
    
    # Set test data
    success_screen.set_user_data({"name": "Juan Pérez"})
    success_screen.set_verification_result("facial", 0.95)
    
    # Show success screen
    ui_manager.show_screen("success")
    
    # Run UI
    try:
        ui_manager.run()
    finally:
        ui_manager.stop()