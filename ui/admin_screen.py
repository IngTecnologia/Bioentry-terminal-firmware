"""
Admin screen UI for the biometric terminal.
Provides configuration, user management, and system monitoring capabilities.
"""

import pygame
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
import asyncio
from enum import Enum

from .base_ui import (UIScreen, UIComponent, UIButton, UILabel, UIRect, UIProgressBar,
                      UIColors, UIFonts, create_centered_rect, create_grid_rect)
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState


class AdminSection(Enum):
    """Admin screen sections"""
    MAIN = "main"
    SYSTEM_STATUS = "system_status"
    USER_MANAGEMENT = "user_management"
    CONFIGURATION = "configuration"
    DIAGNOSTICS = "diagnostics"
    LOGS = "logs"


class SystemInfoPanel(UIComponent):
    """Panel displaying system information"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.system_info = {}
        self.update_interval = 60  # Update every 60 frames (1 second at 60fps)
        self.update_counter = 0
        self._update_info()
    
    def _update_info(self) -> None:
        """Update system information"""
        config = get_config()
        state_manager = get_state_manager()
        
        self.system_info = {
            "Terminal ID": config.api.terminal_id,
            "Status": state_manager.get_current_state().value,
            "Mode": config.operation.mode,
            "Location": config.operation.location_name,
            "Version": "1.0.0",
            "Uptime": self._get_uptime()
        }
    
    def _get_uptime(self) -> str:
        """Get system uptime"""
        # This is a simplified version - in real implementation, 
        # you would track actual system start time
        return "2h 35m"
    
    def update(self) -> None:
        """Update system info periodically"""
        self.update_counter += 1
        if self.update_counter >= self.update_interval:
            self._update_info()
            self.update_counter = 0
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw panel background
        pygame.draw.rect(surface, UIColors.SURFACE, self.rect.get_pygame_rect(), border_radius=8)
        pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect(), width=2, border_radius=8)
        
        # Draw title
        font_title = pygame.font.Font(None, UIFonts.SUBTITLE)
        title_surface = font_title.render("System Information", True, UIColors.PRIMARY)
        title_rect = title_surface.get_rect(x=self.rect.x + 10, y=self.rect.y + 10)
        surface.blit(title_surface, title_rect)
        
        # Draw system info
        font_info = pygame.font.Font(None, UIFonts.BODY)
        y_offset = 45
        
        for key, value in self.system_info.items():
            # Draw key
            key_surface = font_info.render(f"{key}:", True, UIColors.TEXT_SECONDARY)
            key_rect = key_surface.get_rect(x=self.rect.x + 15, y=self.rect.y + y_offset)
            surface.blit(key_surface, key_rect)
            
            # Draw value
            value_surface = font_info.render(str(value), True, UIColors.TEXT_PRIMARY)
            value_rect = value_surface.get_rect(x=self.rect.x + 150, y=self.rect.y + y_offset)
            surface.blit(value_surface, value_rect)
            
            y_offset += 25


class StatisticsPanel(UIComponent):
    """Panel displaying system statistics"""
    
    def __init__(self, rect: UIRect):
        super().__init__(rect)
        self.statistics = {}
        self._update_statistics()
    
    def _update_statistics(self) -> None:
        """Update statistics"""
        # TODO: Get real statistics from database
        self.statistics = {
            "Registered users": 145,
            "Today's access": 23,
            "This week's access": 167,
            "Success rate": "94.2%",
            "Facial recognition": "78%",
            "Fingerprint": "16%",
            "Manual entry": "6%"
        }
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw panel background
        pygame.draw.rect(surface, UIColors.SURFACE, self.rect.get_pygame_rect(), border_radius=8)
        pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect(), width=2, border_radius=8)
        
        # Draw title
        font_title = pygame.font.Font(None, UIFonts.SUBTITLE)
        title_surface = font_title.render("Statistics", True, UIColors.PRIMARY)
        title_rect = title_surface.get_rect(x=self.rect.x + 10, y=self.rect.y + 10)
        surface.blit(title_surface, title_rect)
        
        # Draw statistics
        font_stats = pygame.font.Font(None, UIFonts.BODY)
        y_offset = 45
        
        for key, value in self.statistics.items():
            # Draw key
            key_surface = font_stats.render(f"{key}:", True, UIColors.TEXT_SECONDARY)
            key_rect = key_surface.get_rect(x=self.rect.x + 15, y=self.rect.y + y_offset)
            surface.blit(key_surface, key_rect)
            
            # Draw value
            value_color = UIColors.SUCCESS if isinstance(value, str) and "%" in value else UIColors.TEXT_PRIMARY
            value_surface = font_stats.render(str(value), True, value_color)
            value_rect = value_surface.get_rect(x=self.rect.x + 200, y=self.rect.y + y_offset)
            surface.blit(value_surface, value_rect)
            
            y_offset += 25


class QuickActionsPanel(UIComponent):
    """Panel with quick action buttons"""
    
    def __init__(self, rect: UIRect, on_action: Callable[[str], None]):
        super().__init__(rect)
        self.on_action = on_action
        self.buttons = []
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Setup quick action buttons"""
        actions = [
            ("Sync", "sync"),
            ("Backup DB", "backup"),
            ("Restart", "restart"),
            ("Maintenance", "maintenance")
        ]
        
        button_width = (self.rect.width - 50) // 2
        button_height = 45
        
        for i, (text, action) in enumerate(actions):
            col = i % 2
            row = i // 2
            
            x = self.rect.x + 15 + col * (button_width + 20)
            y = self.rect.y + 45 + row * (button_height + 10)
            
            button = UIButton(
                UIRect(x, y, button_width, button_height),
                text,
                lambda a=action: self.on_action(a),
                "secondary"
            )
            
            self.buttons.append(button)
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw panel background
        pygame.draw.rect(surface, UIColors.SURFACE, self.rect.get_pygame_rect(), border_radius=8)
        pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect(), width=2, border_radius=8)
        
        # Draw title
        font_title = pygame.font.Font(None, UIFonts.SUBTITLE)
        title_surface = font_title.render("Quick Actions", True, UIColors.PRIMARY)
        title_rect = title_surface.get_rect(x=self.rect.x + 10, y=self.rect.y + 10)
        surface.blit(title_surface, title_rect)
        
        # Draw buttons
        for button in self.buttons:
            button.draw(surface)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events for all buttons"""
        for button in self.buttons:
            if button.handle_event(event):
                return True
        return False


class AdminScreen(UIScreen):
    """Admin screen for system configuration and management"""
    
    def __init__(self):
        super().__init__("admin")
        
        # Screen layout constants
        self.SCREEN_WIDTH = 400
        self.SCREEN_HEIGHT = 800
        
        # Components
        self.title_label = None
        self.back_button = None
        self.section_buttons = []
        self.current_section = AdminSection.MAIN
        
        # Panels
        self.system_info_panel = None
        self.statistics_panel = None
        self.quick_actions_panel = None
        
        # State
        self.authenticated = False
        self.auth_start_time = None
        
        # Setup UI
        self._setup_ui()
        
        self.logger.info("Admin screen initialized")
    
    def _setup_ui(self) -> None:
        """Setup all UI components"""
        
        # Title
        self.title_label = UILabel(
            UIRect(20, 20, 300, 40),
            "Administration",
            UIFonts.TITLE,
            UIColors.PRIMARY,
            "left"
        )
        
        # Back button
        self.back_button = UIButton(
            UIRect(320, 20, 60, 40),
            "Back",
            self._on_back_click,
            "outline"
        )
        
        # Section navigation buttons
        sections = [
            ("Status", AdminSection.SYSTEM_STATUS),
            ("Users", AdminSection.USER_MANAGEMENT),
            ("Config", AdminSection.CONFIGURATION),
            ("Diagnostics", AdminSection.DIAGNOSTICS)
        ]
        
        for i, (text, section) in enumerate(sections):
            button = UIButton(
                UIRect(20 + i * 95, 80, 85, 35),
                text,
                lambda s=section: self._switch_section(s),
                "secondary"
            )
            self.section_buttons.append(button)
        
        # System info panel
        self.system_info_panel = SystemInfoPanel(
            UIRect(20, 140, self.SCREEN_WIDTH - 40, 180)
        )
        
        # Statistics panel
        self.statistics_panel = StatisticsPanel(
            UIRect(20, 340, self.SCREEN_WIDTH - 40, 200)
        )
        
        # Quick actions panel
        self.quick_actions_panel = QuickActionsPanel(
            UIRect(20, 560, self.SCREEN_WIDTH - 40, 150),
            self._on_quick_action
        )
        
        # Add components to screen
        self.add_component(self.title_label)
        self.add_component(self.back_button)
        
        for button in self.section_buttons:
            self.add_component(button)
        
        self.add_component(self.system_info_panel)
        self.add_component(self.statistics_panel)
        self.add_component(self.quick_actions_panel)
    
    def _switch_section(self, section: AdminSection) -> None:
        """Switch to a different admin section"""
        self.current_section = section
        self.logger.info(f"Switched to admin section: {section.value}")
        
        # Update section button states
        for i, button in enumerate(self.section_buttons):
            if i == list(AdminSection)[1:].index(section):  # Skip MAIN
                button.style = "primary"
            else:
                button.style = "secondary"
        
        # Show/hide panels based on section
        if section == AdminSection.SYSTEM_STATUS:
            self.system_info_panel.set_visible(True)
            self.statistics_panel.set_visible(True)
            self.quick_actions_panel.set_visible(True)
        elif section == AdminSection.USER_MANAGEMENT:
            self.system_info_panel.set_visible(False)
            self.statistics_panel.set_visible(True)
            self.quick_actions_panel.set_visible(False)
        elif section == AdminSection.CONFIGURATION:
            self.system_info_panel.set_visible(True)
            self.statistics_panel.set_visible(False)
            self.quick_actions_panel.set_visible(True)
        elif section == AdminSection.DIAGNOSTICS:
            self.system_info_panel.set_visible(True)
            self.statistics_panel.set_visible(False)
            self.quick_actions_panel.set_visible(False)
    
    def _on_back_click(self) -> None:
        """Handle back button click"""
        self.logger.info("Admin screen back button clicked")
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.IDLE, "admin_back_clicked")
        )
    
    def _on_quick_action(self, action: str) -> None:
        """Handle quick action button click"""
        self.logger.info(f"Quick action clicked: {action}")
        
        if action == "sync":
            self._perform_sync()
        elif action == "backup":
            self._perform_backup()
        elif action == "restart":
            self._perform_restart()
        elif action == "maintenance":
            self._enter_maintenance_mode()
    
    def _perform_sync(self) -> None:
        """Perform data synchronization"""
        self.logger.info("Performing data synchronization")
        # TODO: Implement actual sync logic
        
        # Show progress feedback
        self._show_action_feedback("Synchronizing data...", 3.0)
    
    def _perform_backup(self) -> None:
        """Perform database backup"""
        self.logger.info("Performing database backup")
        # TODO: Implement actual backup logic
        
        self._show_action_feedback("Creating backup...", 2.0)
    
    def _perform_restart(self) -> None:
        """Perform system restart"""
        self.logger.info("Performing system restart")
        
        # Show confirmation dialog
        self._show_action_feedback("Restarting system...", 5.0)
        
        # TODO: Implement actual restart logic
    
    def _enter_maintenance_mode(self) -> None:
        """Enter maintenance mode"""
        self.logger.info("Entering maintenance mode")
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.MAINTENANCE, "admin_maintenance_requested")
        )
    
    def _show_action_feedback(self, message: str, duration: float) -> None:
        """Show feedback for an action"""
        # TODO: Implement modal feedback dialog
        self.logger.info(f"Action feedback: {message}")
    
    def _authenticate_admin(self) -> bool:
        """Authenticate admin access"""
        # TODO: Implement proper admin authentication
        # For now, just return True
        return True
    
    def update(self) -> None:
        """Update screen state"""
        # Update panels
        if self.system_info_panel.visible:
            self.system_info_panel.update()
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event"""
        # Let quick actions panel handle events
        if self.quick_actions_panel.visible and self.quick_actions_panel.handle_event(event):
            return True
        
        # Handle keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._on_back_click()
                return True
            elif event.key == pygame.K_F5:
                self._perform_sync()
                return True
            elif event.key == pygame.K_F12:
                self._perform_backup()
                return True
        
        return super().handle_event(event)
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the admin screen"""
        # Draw background
        surface.fill(UIColors.BACKGROUND)
        
        # Draw header section
        header_rect = pygame.Rect(0, 0, self.SCREEN_WIDTH, 130)
        pygame.draw.rect(surface, UIColors.SURFACE, header_rect)
        pygame.draw.line(surface, UIColors.BORDER, (0, 130), (self.SCREEN_WIDTH, 130), 2)
        
        # Draw section navigation background
        nav_rect = pygame.Rect(10, 75, self.SCREEN_WIDTH - 20, 45)
        pygame.draw.rect(surface, UIColors.BACKGROUND, nav_rect, border_radius=8)
        
        # Draw all components
        super().draw(surface)
        
        # Draw section-specific content
        self._draw_section_content(surface)
        
        # Draw authentication overlay if not authenticated
        if not self.authenticated:
            self._draw_auth_overlay(surface)
    
    def _draw_section_content(self, surface: pygame.Surface) -> None:
        """Draw content specific to current section"""
        if self.current_section == AdminSection.USER_MANAGEMENT:
            self._draw_user_management_content(surface)
        elif self.current_section == AdminSection.CONFIGURATION:
            self._draw_configuration_content(surface)
        elif self.current_section == AdminSection.DIAGNOSTICS:
            self._draw_diagnostics_content(surface)
    
    def _draw_user_management_content(self, surface: pygame.Surface) -> None:
        """Draw user management specific content"""
        # Placeholder for user management UI
        font = pygame.font.Font(None, UIFonts.BODY)
        text = "User management in development"
        text_surface = font.render(text, True, UIColors.TEXT_SECONDARY)
        text_rect = text_surface.get_rect(center=(self.SCREEN_WIDTH // 2, 400))
        surface.blit(text_surface, text_rect)
    
    def _draw_configuration_content(self, surface: pygame.Surface) -> None:
        """Draw configuration specific content"""
        # Placeholder for configuration UI
        font = pygame.font.Font(None, UIFonts.BODY)
        text = "System configuration in development"
        text_surface = font.render(text, True, UIColors.TEXT_SECONDARY)
        text_rect = text_surface.get_rect(center=(self.SCREEN_WIDTH // 2, 400))
        surface.blit(text_surface, text_rect)
    
    def _draw_diagnostics_content(self, surface: pygame.Surface) -> None:
        """Draw diagnostics specific content"""
        # Simple hardware status display
        y_offset = 350
        font = pygame.font.Font(None, UIFonts.BODY)
        
        # Hardware status
        hardware_status = [
            ("Camera", "OK", UIColors.SUCCESS),
            ("Fingerprint sensor", "OK", UIColors.SUCCESS),
            ("Proximity sensor", "OK", UIColors.SUCCESS),
            ("Connectivity", "Intermittent", UIColors.WARNING),
            ("Database", "OK", UIColors.SUCCESS)
        ]
        
        for component, status, color in hardware_status:
            # Component name
            name_surface = font.render(f"{component}:", True, UIColors.TEXT_PRIMARY)
            name_rect = name_surface.get_rect(x=30, y=y_offset)
            surface.blit(name_surface, name_rect)
            
            # Status
            status_surface = font.render(status, True, color)
            status_rect = status_surface.get_rect(x=200, y=y_offset)
            surface.blit(status_surface, status_rect)
            
            y_offset += 25
    
    def _draw_auth_overlay(self, surface: pygame.Surface) -> None:
        """Draw authentication overlay"""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(UIColors.TEXT_DISABLED)
        surface.blit(overlay, (0, 0))
        
        # Auth dialog
        dialog_rect = pygame.Rect(50, 250, 300, 200)
        pygame.draw.rect(surface, UIColors.SURFACE, dialog_rect, border_radius=10)
        pygame.draw.rect(surface, UIColors.BORDER, dialog_rect, width=2, border_radius=10)
        
        # Auth message
        font = pygame.font.Font(None, UIFonts.SUBTITLE)
        auth_text = "Administrator access"
        auth_surface = font.render(auth_text, True, UIColors.TEXT_PRIMARY)
        auth_rect = auth_surface.get_rect(center=(200, 320))
        surface.blit(auth_surface, auth_rect)
        
        # Instructions
        font_small = pygame.font.Font(None, UIFonts.BODY)
        instr_text = "Authentication required"
        instr_surface = font_small.render(instr_text, True, UIColors.TEXT_SECONDARY)
        instr_rect = instr_surface.get_rect(center=(200, 350))
        surface.blit(instr_surface, instr_rect)
        
        # Temporary bypass message
        bypass_text = "Press any key to continue"
        bypass_surface = font_small.render(bypass_text, True, UIColors.WARNING)
        bypass_rect = bypass_surface.get_rect(center=(200, 400))
        surface.blit(bypass_surface, bypass_rect)
    
    def on_activate(self) -> None:
        """Called when screen becomes active"""
        super().on_activate()
        
        # Reset to main section
        self.current_section = AdminSection.MAIN
        self._switch_section(AdminSection.SYSTEM_STATUS)
        
        # Check authentication
        if not self._authenticate_admin():
            self.authenticated = False
            self.auth_start_time = datetime.now()
        else:
            self.authenticated = True
    
    def on_deactivate(self) -> None:
        """Called when screen becomes inactive"""
        super().on_deactivate()
        self.authenticated = False
        self.auth_start_time = None


if __name__ == "__main__":
    # Test the admin screen
    from .base_ui import get_ui_manager
    
    ui_manager = get_ui_manager()
    
    # Create and register admin screen
    admin_screen = AdminScreen()
    ui_manager.register_screen(admin_screen)
    
    # Show admin screen
    ui_manager.show_screen("admin")
    
    # Run UI
    try:
        ui_manager.run()
    finally:
        ui_manager.stop()