"""
UI module for the biometric terminal.
Provides all user interface components and screens.
"""

from .base_ui import (
    UIManager, UIScreen, UIComponent, UIButton, UILabel, UIImage, UIProgressBar,
    UIRect, UIColors, UIFonts, get_ui_manager, create_centered_rect, create_grid_rect
)

from .main_screen import MainScreen, CameraPreviewComponent, StatusIndicator
from .success_screen import SuccessScreen, SuccessIcon, WelcomeMessage, AccessInfo
from .manual_entry_screen import ManualEntryScreen, NumericKeypad, DocumentIDField
from .admin_screen import AdminScreen, SystemInfoPanel, StatisticsPanel, QuickActionsPanel

__all__ = [
    # Base UI framework
    'UIManager', 'UIScreen', 'UIComponent', 'UIButton', 'UILabel', 'UIImage', 
    'UIProgressBar', 'UIRect', 'UIColors', 'UIFonts', 'get_ui_manager',
    'create_centered_rect', 'create_grid_rect',
    
    # Screen implementations
    'MainScreen', 'SuccessScreen', 'ManualEntryScreen', 'AdminScreen',
    
    # Specialized components
    'CameraPreviewComponent', 'StatusIndicator', 'SuccessIcon', 'WelcomeMessage',
    'AccessInfo', 'NumericKeypad', 'DocumentIDField', 'SystemInfoPanel',
    'StatisticsPanel', 'QuickActionsPanel'
]

def initialize_ui() -> UIManager:
    """
    Initialize the complete UI system with all screens.
    
    Returns:
        UIManager: Configured UI manager with all screens registered
    """
    ui_manager = get_ui_manager()
    
    # Create and register all screens
    main_screen = MainScreen()
    success_screen = SuccessScreen()
    manual_entry_screen = ManualEntryScreen()
    admin_screen = AdminScreen()
    
    ui_manager.register_screen(main_screen)
    ui_manager.register_screen(success_screen)
    ui_manager.register_screen(manual_entry_screen)
    ui_manager.register_screen(admin_screen)
    
    # Set initial screen
    ui_manager.show_screen("main")
    
    return ui_manager


def get_screen_references() -> dict:
    """
    Get references to all registered screens for external integration.
    
    Returns:
        dict: Dictionary mapping screen names to screen instances
    """
    ui_manager = get_ui_manager()
    return {
        'main': ui_manager.get_screen('main'),
        'success': ui_manager.get_screen('success'),
        'manual_entry': ui_manager.get_screen('manual_entry'),
        'admin': ui_manager.get_screen('admin')
    }