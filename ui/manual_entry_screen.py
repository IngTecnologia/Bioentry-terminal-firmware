"""
Manual entry screen UI for the biometric terminal.
Provides numeric keypad for document ID entry when biometric verification fails.
"""

import pygame
from typing import Optional, Dict, Any, Callable
from datetime import datetime
import asyncio
import re

from .base_ui import (UIScreen, UIComponent, UIButton, UILabel, UIRect, 
                      UIColors, UIFonts, create_centered_rect, create_grid_rect)
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData


class NumericKeypad(UIComponent):
    """Numeric keypad component for document ID entry"""
    
    def __init__(self, rect: UIRect, on_key_press: Callable[[str], None]):
        super().__init__(rect)
        self.on_key_press = on_key_press
        self.buttons = []
        self._setup_keypad()
        
    def _setup_keypad(self) -> None:
        """Setup keypad buttons"""
        # Keypad layout
        keypad_layout = [
            ['1', '2', '3'],
            ['4', '5', '6'],
            ['7', '8', '9'],
            ['DEL', '0', 'OK']
        ]
        
        button_width = (self.rect.width - 30) // 3  # 3 columns with margins
        button_height = (self.rect.height - 40) // 4  # 4 rows with margins
        
        for row_idx, row in enumerate(keypad_layout):
            for col_idx, key in enumerate(row):
                x = self.rect.x + 10 + col_idx * (button_width + 5)
                y = self.rect.y + 10 + row_idx * (button_height + 5)
                
                # Determine button style
                if key == 'DEL':
                    style = "outline"
                    text_color = UIColors.ERROR
                elif key == 'OK':
                    style = "primary"
                    text_color = UIColors.SURFACE
                else:
                    style = "secondary"
                    text_color = UIColors.SURFACE
                
                button = UIButton(
                    UIRect(x, y, button_width, button_height),
                    key,
                    lambda k=key: self._on_button_click(k),
                    style
                )
                
                self.buttons.append(button)
    
    def _on_button_click(self, key: str) -> None:
        """Handle keypad button click"""
        if self.on_key_press:
            self.on_key_press(key)
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw keypad background
        pygame.draw.rect(surface, UIColors.SURFACE, self.rect.get_pygame_rect(), border_radius=10)
        pygame.draw.rect(surface, UIColors.BORDER, self.rect.get_pygame_rect(), width=2, border_radius=10)
        
        # Draw all buttons
        for button in self.buttons:
            button.draw(surface)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events for all buttons"""
        for button in self.buttons:
            if button.handle_event(event):
                return True
        return False
    
    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable all keypad buttons"""
        super().set_enabled(enabled)
        for button in self.buttons:
            button.set_enabled(enabled)


class DocumentIDField(UIComponent):
    """Document ID input field component"""
    
    def __init__(self, rect: UIRect, max_length: int = 12):
        super().__init__(rect)
        self.text = ""
        self.max_length = max_length
        self.cursor_visible = True
        self.cursor_blink_time = 0
        self.is_valid = True
        self.error_message = ""
        
    def set_text(self, text: str) -> None:
        """Set the field text"""
        self.text = text[:self.max_length]
        self._validate_text()
        
    def add_character(self, char: str) -> None:
        """Add a character to the field"""
        if len(self.text) < self.max_length and char.isdigit():
            self.text += char
            self._validate_text()
    
    def remove_character(self) -> None:
        """Remove the last character"""
        if self.text:
            self.text = self.text[:-1]
            self._validate_text()
    
    def clear(self) -> None:
        """Clear the field"""
        self.text = ""
        self._validate_text()
    
    def _validate_text(self) -> None:
        """Validate the document ID"""
        if not self.text:
            self.is_valid = True
            self.error_message = ""
            return
        
        # Basic validation: at least 6 digits, only numbers
        if len(self.text) < 6:
            self.is_valid = False
            self.error_message = "Minimum 6 digits"
        elif not self.text.isdigit():
            self.is_valid = False
            self.error_message = "Numbers only"
        else:
            self.is_valid = True
            self.error_message = ""
    
    def update(self) -> None:
        """Update cursor blink animation"""
        self.cursor_blink_time += 1
        if self.cursor_blink_time >= 30:  # Blink every 30 frames (0.5s at 60fps)
            self.cursor_visible = not self.cursor_visible
            self.cursor_blink_time = 0
    
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        
        # Draw field background
        bg_color = UIColors.SURFACE
        border_color = UIColors.ERROR if not self.is_valid else UIColors.BORDER
        
        if self.focused:
            border_color = UIColors.PRIMARY
        
        pygame.draw.rect(surface, bg_color, self.rect.get_pygame_rect(), border_radius=8)
        pygame.draw.rect(surface, border_color, self.rect.get_pygame_rect(), width=3, border_radius=8)
        
        # Draw text
        font = pygame.font.Font(None, UIFonts.TITLE)
        text_color = UIColors.TEXT_PRIMARY if self.is_valid else UIColors.ERROR
        
        # Display text or placeholder
        display_text = self.text if self.text else "000000000"
        text_surface = font.render(display_text, True, text_color)
        
        # Center text in field
        text_rect = text_surface.get_rect(center=(self.rect.center_x(), self.rect.center_y()))
        surface.blit(text_surface, text_rect)
        
        # Draw cursor
        if self.focused and self.cursor_visible and self.text:
            cursor_x = text_rect.right + 5
            cursor_y = text_rect.centery
            pygame.draw.line(surface, UIColors.PRIMARY, 
                           (cursor_x, cursor_y - 15), (cursor_x, cursor_y + 15), 2)
        
        # Draw placeholder dots for empty positions
        if len(self.text) < 8:  # Show guidance for common ID length
            font_small = pygame.font.Font(None, UIFonts.CAPTION)
            remaining = 8 - len(self.text)
            dots = "." * remaining
            dots_surface = font_small.render(dots, True, UIColors.TEXT_DISABLED)
            dots_rect = dots_surface.get_rect(left=text_rect.right + 10, centery=text_rect.centery)
            surface.blit(dots_surface, dots_rect)


class ManualEntryScreen(UIScreen):
    """Manual entry screen for document ID input"""
    
    def __init__(self):
        super().__init__("manual_entry")
        
        # Screen layout constants
        self.SCREEN_WIDTH = 400
        self.SCREEN_HEIGHT = 800
        self.VERIFICATION_TIMEOUT = 10.0  # seconds
        
        # Components
        self.title_label = None
        self.instruction_label = None
        self.document_field = None
        self.keypad = None
        self.submit_button = None
        self.cancel_button = None
        self.error_label = None
        self.attempts_label = None
        
        # State
        self.verification_start_time = None
        self.current_attempts = 0
        self.max_attempts = 3
        self.is_verifying = False
        
        # Setup UI
        self._setup_ui()
        
        # State callbacks
        self.state_manager.on_state_enter(SystemState.MANUAL_ENTRY, self._on_manual_entry_state)
        
        self.logger.info("Manual entry screen initialized")
    
    def _setup_ui(self) -> None:
        """Setup all UI components"""
        
        # Title
        self.title_label = UILabel(
            UIRect(20, 20, self.SCREEN_WIDTH - 40, 40),
            "Manual Entry",
            UIFonts.TITLE,
            UIColors.PRIMARY,
            "center"
        )
        
        # Instructions
        self.instruction_label = UILabel(
            UIRect(20, 80, self.SCREEN_WIDTH - 40, 60),
            "Enter your document number\nand press OK to continue",
            UIFonts.BODY,
            UIColors.TEXT_PRIMARY,
            "center"
        )
        
        # Document ID field
        self.document_field = DocumentIDField(
            create_centered_rect(300, 60, y_offset=-200)
        )
        
        # Keypad
        self.keypad = NumericKeypad(
            create_centered_rect(280, 300, y_offset=-50),
            self._on_keypad_press
        )
        
        # Submit button
        self.submit_button = UIButton(
            create_centered_rect(250, 50, y_offset=180),
            "Verify Document",
            self._on_submit_click,
            "primary"
        )
        self.submit_button.set_enabled(False)
        
        # Cancel button
        self.cancel_button = UIButton(
            create_centered_rect(200, 40, y_offset=250),
            "Cancel",
            self._on_cancel_click,
            "outline"
        )
        
        # Error label
        self.error_label = UILabel(
            create_centered_rect(350, 30, y_offset=300),
            "",
            UIFonts.BODY,
            UIColors.ERROR,
            "center"
        )
        self.error_label.set_visible(False)
        
        # Attempts label
        self.attempts_label = UILabel(
            create_centered_rect(350, 25, y_offset=340),
            "",
            UIFonts.CAPTION,
            UIColors.TEXT_SECONDARY,
            "center"
        )
        
        # Add components to screen
        self.add_component(self.title_label)
        self.add_component(self.instruction_label)
        self.add_component(self.document_field)
        self.add_component(self.keypad)
        self.add_component(self.submit_button)
        self.add_component(self.cancel_button)
        self.add_component(self.error_label)
        self.add_component(self.attempts_label)
    
    def _on_manual_entry_state(self, state: SystemState, data: StateData) -> None:
        """Handle manual entry state"""
        self.current_attempts = self.state_manager.get_attempts("manual_entry")
        self._update_attempts_display()
        
        # Clear previous input
        self.document_field.clear()
        self.document_field.focused = True
        self.error_label.set_visible(False)
        self.submit_button.set_enabled(False)
        
        # Enable keypad
        self.keypad.set_enabled(True)
        
        self.logger.info("Manual entry screen activated", 
                        attempts=self.current_attempts, 
                        max_attempts=self.max_attempts)
    
    def _on_keypad_press(self, key: str) -> None:
        """Handle keypad button press"""
        if self.is_verifying:
            return
        
        if key == 'DEL':
            self.document_field.remove_character()
        elif key == 'OK':
            self._submit_document_id()
        elif key.isdigit():
            self.document_field.add_character(key)
        
        # Update submit button state
        self.submit_button.set_enabled(
            len(self.document_field.text) >= 6 and self.document_field.is_valid
        )
        
        # Clear error message when user starts typing
        if key.isdigit() and self.error_label.visible:
            self.error_label.set_visible(False)
    
    def _on_submit_click(self) -> None:
        """Handle submit button click"""
        self._submit_document_id()
    
    def _on_cancel_click(self) -> None:
        """Handle cancel button click"""
        self.logger.info("Manual entry cancelled")
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.IDLE, "manual_entry_cancelled")
        )
    
    def _submit_document_id(self) -> None:
        """Submit document ID for verification"""
        if not self.document_field.is_valid or len(self.document_field.text) < 6:
            self._show_error("Invalid document")
            return
        
        if self.is_verifying:
            return
        
        document_id = self.document_field.text
        self.logger.info("Document ID submitted", document_id=document_id)
        
        # Start verification
        self.is_verifying = True
        self.verification_start_time = datetime.now()
        
        # Update UI
        self.submit_button.set_enabled(False)
        self.keypad.set_enabled(False)
        self.instruction_label.set_text("Verifying document...")
        
        # TODO: Integrate with verification service
        # For now, simulate verification
        self._simulate_verification(document_id)
    
    def _simulate_verification(self, document_id: str) -> None:
        """Simulate document verification (for testing)"""
        import threading
        import time
        
        def verify():
            time.sleep(2)  # Simulate verification delay
            
            # Mock verification logic
            if document_id == "12345678":
                # Success
                self._on_verification_success({
                    "document_id": document_id,
                    "name": "Test User",
                    "employee_id": "EMP001"
                })
            else:
                # Failure
                self._on_verification_failure("Document not found")
        
        threading.Thread(target=verify, daemon=True).start()
    
    def _on_verification_success(self, user_data: Dict[str, Any]) -> None:
        """Handle successful verification"""
        self.is_verifying = False
        self.logger.info("Manual verification successful", user_data=user_data)
        
        # Create state data
        state_data = StateData(
            user_data=user_data,
            verification_result={
                "method": "manual",
                "confidence": 1.0,
                "document_id": user_data["document_id"]
            }
        )
        
        # Transition to confirmation
        asyncio.create_task(
            self.state_manager.transition_to(SystemState.CONFIRMATION, 
                                           "manual_verification_success", state_data)
        )
    
    def _on_verification_failure(self, error_message: str) -> None:
        """Handle verification failure"""
        self.is_verifying = False
        self.current_attempts = self.state_manager.increment_attempts("manual_entry")
        
        self.logger.warning("Manual verification failed", 
                          error_message=error_message,
                          attempts=self.current_attempts)
        
        # Update UI
        self._show_error(error_message)
        self._update_attempts_display()
        
        # Check if max attempts reached
        if self.current_attempts >= self.max_attempts:
            self._show_error("Maximum attempts reached")
            self.keypad.set_enabled(False)
            self.submit_button.set_enabled(False)
            
            # Transition to error state after delay
            def transition_to_error():
                time.sleep(3)
                asyncio.create_task(
                    self.state_manager.transition_to(SystemState.ERROR, 
                                                   "max_manual_attempts_reached")
                )
            
            import threading
            threading.Thread(target=transition_to_error, daemon=True).start()
        else:
            # Re-enable input
            self.keypad.set_enabled(True)
            self.instruction_label.set_text("Enter your document number\nand press OK to continue")
            self.submit_button.set_enabled(
                len(self.document_field.text) >= 6 and self.document_field.is_valid
            )
    
    def _show_error(self, message: str) -> None:
        """Show error message"""
        self.error_label.set_text(message)
        self.error_label.set_visible(True)
    
    def _update_attempts_display(self) -> None:
        """Update attempts display"""
        remaining = self.max_attempts - self.current_attempts
        if remaining > 0:
            self.attempts_label.set_text(f"Remaining attempts: {remaining}")
        else:
            self.attempts_label.set_text("No attempts remaining")
    
    def update(self) -> None:
        """Update screen state"""
        # Update document field cursor
        self.document_field.update()
        
        # Check for verification timeout
        if (self.is_verifying and self.verification_start_time and 
            (datetime.now() - self.verification_start_time).total_seconds() > self.VERIFICATION_TIMEOUT):
            self._on_verification_failure("Verification timeout")
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame event"""
        # Let keypad handle events first
        if self.keypad.handle_event(event):
            return True
        
        # Handle keyboard input
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                if self.submit_button.enabled:
                    self._submit_document_id()
                return True
            elif event.key == pygame.K_ESCAPE:
                self._on_cancel_click()
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.document_field.remove_character()
                return True
            elif event.unicode.isdigit():
                self.document_field.add_character(event.unicode)
                return True
        
        return super().handle_event(event)
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the manual entry screen"""
        # Draw background
        surface.fill(UIColors.BACKGROUND)
        
        # Draw header section
        header_rect = pygame.Rect(0, 0, self.SCREEN_WIDTH, 140)
        pygame.draw.rect(surface, UIColors.SURFACE, header_rect)
        pygame.draw.line(surface, UIColors.BORDER, (0, 140), (self.SCREEN_WIDTH, 140), 2)
        
        # Draw all components
        super().draw(surface)
        
        # Draw loading overlay if verifying
        if self.is_verifying:
            overlay = pygame.Surface((self.SCREEN_WIDTH, self.SCREEN_HEIGHT))
            overlay.set_alpha(128)
            overlay.fill(UIColors.TEXT_DISABLED)
            surface.blit(overlay, (0, 0))
            
            # Draw loading spinner
            center_x = self.SCREEN_WIDTH // 2
            center_y = self.SCREEN_HEIGHT // 2
            
            # Simple spinning indicator
            import math
            angle = (pygame.time.get_ticks() / 5) % 360
            
            for i in range(8):
                dot_angle = angle + i * 45
                dot_x = center_x + 30 * math.cos(math.radians(dot_angle))
                dot_y = center_y + 30 * math.sin(math.radians(dot_angle))
                
                alpha = 255 - (i * 30)
                alpha = max(50, alpha)
                
                pygame.draw.circle(surface, UIColors.PRIMARY, (int(dot_x), int(dot_y)), 4)
    
    def on_activate(self) -> None:
        """Called when screen becomes active"""
        super().on_activate()
        self.document_field.focused = True
        self.is_verifying = False
        
    def on_deactivate(self) -> None:
        """Called when screen becomes inactive"""
        super().on_deactivate()
        self.document_field.focused = False
        self.is_verifying = False
        self.verification_start_time = None


if __name__ == "__main__":
    # Test the manual entry screen
    from .base_ui import get_ui_manager
    
    ui_manager = get_ui_manager()
    
    # Create and register manual entry screen
    manual_screen = ManualEntryScreen()
    ui_manager.register_screen(manual_screen)
    
    # Show manual entry screen
    ui_manager.show_screen("manual_entry")
    
    # Run UI
    try:
        ui_manager.run()
    finally:
        ui_manager.stop()