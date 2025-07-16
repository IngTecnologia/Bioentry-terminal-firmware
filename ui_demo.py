#!/usr/bin/env python3
"""
UI Demo for the BioEntry Terminal.
Demonstrates the complete UI system with mock data and interactions.
"""

import pygame
import numpy as np
import asyncio
import threading
import time
from datetime import datetime
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui import initialize_ui, get_screen_references
from utils.state_manager import get_state_manager, SystemState, StateData
from utils.config import get_config
from utils.logger import get_logger, setup_logging


class MockCameraManager:
    """Mock camera manager for demonstration"""
    
    def __init__(self):
        self.running = False
        self.frame_callback = None
        self.face_callback = None
        
    def start(self, frame_callback=None, face_callback=None):
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
        frame_count = 0
        
        while self.running:
            # Generate a gradient frame with some variation
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Create a gradient background
            for y in range(480):
                for x in range(640):
                    r = int(50 + (x / 640) * 100 + np.sin(frame_count * 0.1) * 20)
                    g = int(70 + (y / 480) * 80 + np.cos(frame_count * 0.08) * 15)
                    b = int(90 + ((x + y) / (640 + 480)) * 60)
                    
                    frame[y, x] = [max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))]
            
            # Add some "face detection" simulation
            if frame_count % 60 < 30:  # Show face detection for half the time
                # Draw a simple face-like rectangle
                cv2_available = True
                try:
                    import cv2
                    cv2.rectangle(frame, (250, 180), (390, 300), (255, 255, 255), 2)
                    cv2.putText(frame, "MOCK FACE", (270, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                except ImportError:
                    cv2_available = False
                
                if self.face_callback:
                    # Send normalized face detection coordinates
                    face_boxes = [(0.39, 0.375, 0.22, 0.25)]  # (x, y, w, h) normalized
                    self.face_callback(face_boxes)
            
            if self.frame_callback:
                self.frame_callback(frame)
            
            frame_count += 1
            time.sleep(1/15)  # 15 FPS


class MockVerificationService:
    """Mock verification service for demonstration"""
    
    def __init__(self):
        self.logger = get_logger()
        
    async def verify_facial(self, image_data):
        """Mock facial verification"""
        await asyncio.sleep(2)  # Simulate processing time
        
        # Mock verification result
        success = np.random.random() > 0.3  # 70% success rate
        
        if success:
            return {
                "success": True,
                "user_data": {
                    "document_id": "12345678",
                    "name": "Usuario Demo",
                    "employee_id": "EMP001",
                    "department": "Desarrollo"
                },
                "confidence": 0.92,
                "method": "facial"
            }
        else:
            return {
                "success": False,
                "error": "No se pudo verificar el rostro",
                "confidence": 0.45
            }
    
    async def verify_fingerprint(self, template_id):
        """Mock fingerprint verification"""
        await asyncio.sleep(1.5)  # Simulate processing time
        
        success = np.random.random() > 0.2  # 80% success rate
        
        if success:
            return {
                "success": True,
                "user_data": {
                    "document_id": "87654321",
                    "name": "Usuario Huella",
                    "employee_id": "EMP002",
                    "department": "Operaciones"
                },
                "confidence": 0.98,
                "method": "fingerprint"
            }
        else:
            return {
                "success": False,
                "error": "Huella no reconocida",
                "confidence": 0.25
            }
    
    async def verify_manual(self, document_id):
        """Mock manual verification"""
        await asyncio.sleep(1)  # Simulate database lookup
        
        # Predefined test users
        test_users = {
            "12345678": {
                "document_id": "12345678",
                "name": "Usuario Manual",
                "employee_id": "EMP003",
                "department": "Administración"
            },
            "11111111": {
                "document_id": "11111111",
                "name": "Juan Pérez",
                "employee_id": "EMP004",
                "department": "Ventas"
            }
        }
        
        if document_id in test_users:
            return {
                "success": True,
                "user_data": test_users[document_id],
                "confidence": 1.0,
                "method": "manual"
            }
        else:
            return {
                "success": False,
                "error": "Documento no encontrado",
                "confidence": 0.0
            }


class TerminalDemo:
    """Main demo application"""
    
    def __init__(self):
        # Setup logging
        setup_logging()
        self.logger = get_logger()
        self.config = get_config()
        
        # Initialize components
        self.state_manager = get_state_manager()
        self.ui_manager = initialize_ui()
        self.screens = get_screen_references()
        
        # Mock services
        self.camera_manager = MockCameraManager()
        self.verification_service = MockVerificationService()
        
        # State
        self.running = True
        
        # Setup integrations
        self._setup_camera_integration()
        self._setup_state_callbacks()
        
        self.logger.info("Terminal demo initialized")
    
    def _setup_camera_integration(self):
        """Setup camera integration with main screen"""
        main_screen = self.screens['main']
        if main_screen:
            self.camera_manager.start(
                frame_callback=main_screen.set_camera_frame,
                face_callback=main_screen.set_face_detections
            )
    
    def _setup_state_callbacks(self):
        """Setup state management callbacks"""
        # Activation simulation
        self.state_manager.on_state_enter(SystemState.ACTIVATION, self._on_activation)
        self.state_manager.on_state_enter(SystemState.FACIAL_RECOGNITION, self._on_facial_recognition)
        self.state_manager.on_state_enter(SystemState.FINGERPRINT_VERIFICATION, self._on_fingerprint_verification)
        
        # Simulate proximity detection
        threading.Thread(target=self._proximity_simulator, daemon=True).start()
        
        # Simulate automatic state transitions
        threading.Thread(target=self._auto_state_manager, daemon=True).start()
    
    def _proximity_simulator(self):
        """Simulate proximity sensor detection"""
        last_activation = 0
        
        while self.running:
            current_time = time.time()
            current_state = self.state_manager.get_current_state()
            
            # Simulate user approaching every 15-30 seconds
            if (current_state == SystemState.IDLE and 
                current_time - last_activation > np.random.uniform(15, 30)):
                
                self.logger.info("Proximity detected - activating terminal")
                asyncio.run_coroutine_threadsafe(
                    self.state_manager.transition_to(SystemState.ACTIVATION, "proximity_detected"),
                    asyncio.get_event_loop()
                )
                last_activation = current_time
            
            time.sleep(1)
    
    def _auto_state_manager(self):
        """Manage automatic state transitions"""
        while self.running:
            current_state = self.state_manager.get_current_state()
            duration = self.state_manager.get_state_duration()
            
            # Auto-progress from activation to facial recognition
            if current_state == SystemState.ACTIVATION and duration > 2:
                asyncio.run_coroutine_threadsafe(
                    self.state_manager.transition_to(SystemState.FACIAL_RECOGNITION, "auto_progression"),
                    asyncio.get_event_loop()
                )
            
            # Timeout handling
            elif current_state == SystemState.FACIAL_RECOGNITION and duration > 8:
                # Try fingerprint after facial recognition timeout
                asyncio.run_coroutine_threadsafe(
                    self.state_manager.transition_to(SystemState.FINGERPRINT_VERIFICATION, "facial_timeout"),
                    asyncio.get_event_loop()
                )
            
            elif current_state == SystemState.FINGERPRINT_VERIFICATION and duration > 6:
                # Return to idle after fingerprint timeout
                asyncio.run_coroutine_threadsafe(
                    self.state_manager.transition_to(SystemState.IDLE, "fingerprint_timeout"),
                    asyncio.get_event_loop()
                )
            
            time.sleep(0.5)
    
    async def _on_activation(self, state, data):
        """Handle activation state"""
        self.logger.info("Terminal activated")
    
    async def _on_facial_recognition(self, state, data):
        """Handle facial recognition state"""
        self.logger.info("Starting facial recognition")
        
        # Simulate facial recognition after a delay
        await asyncio.sleep(3)
        
        if self.state_manager.get_current_state() == SystemState.FACIAL_RECOGNITION:
            result = await self.verification_service.verify_facial(None)
            
            if result["success"]:
                # Create success state data
                state_data = StateData(
                    user_data=result["user_data"],
                    verification_result=result
                )
                
                await self.state_manager.transition_to(
                    SystemState.CONFIRMATION, "facial_verification_success", state_data
                )
            else:
                # Try fingerprint verification
                await self.state_manager.transition_to(
                    SystemState.FINGERPRINT_VERIFICATION, "facial_verification_failed"
                )
    
    async def _on_fingerprint_verification(self, state, data):
        """Handle fingerprint verification state"""
        self.logger.info("Starting fingerprint verification")
        
        # Simulate fingerprint verification after a delay
        await asyncio.sleep(2)
        
        if self.state_manager.get_current_state() == SystemState.FINGERPRINT_VERIFICATION:
            result = await self.verification_service.verify_fingerprint(1)
            
            if result["success"]:
                # Create success state data
                state_data = StateData(
                    user_data=result["user_data"],
                    verification_result=result
                )
                
                await self.state_manager.transition_to(
                    SystemState.CONFIRMATION, "fingerprint_verification_success", state_data
                )
            else:
                # Return to idle after failed verification
                await self.state_manager.transition_to(
                    SystemState.IDLE, "fingerprint_verification_failed"
                )
    
    def run(self):
        """Run the demo application"""
        self.logger.info("Starting terminal demo")
        
        # Show instructions
        print("\n" + "="*60)
        print("BioEntry Terminal Demo")
        print("="*60)
        print("Controles:")
        print("  ESC - Salir")
        print("  F1  - Activar terminal manualmente")
        print("  F2  - Ir a ingreso manual")
        print("  F3  - Ir a pantalla de administración")
        print("  F4  - Simular éxito de verificación")
        print("  F5  - Volver a pantalla principal")
        print("="*60)
        print("El terminal se activará automáticamente cada 15-30 segundos")
        print("Funcionalidades demostradas:")
        print("- Reconocimiento facial (70% éxito)")
        print("- Verificación de huella (80% éxito)")
        print("- Ingreso manual (documentos: 12345678, 11111111)")
        print("- Panel de administración")
        print("="*60)
        
        try:
            # Run UI in main thread
            clock = pygame.time.Clock()
            
            while self.running:
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    
                    # Handle demo shortcuts
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.running = False
                        elif event.key == pygame.K_F1:
                            asyncio.create_task(
                                self.state_manager.transition_to(SystemState.ACTIVATION, "manual_activation")
                            )
                        elif event.key == pygame.K_F2:
                            asyncio.create_task(
                                self.state_manager.transition_to(SystemState.MANUAL_ENTRY, "demo_manual")
                            )
                        elif event.key == pygame.K_F3:
                            self.ui_manager.show_screen("admin")
                        elif event.key == pygame.K_F4:
                            # Simulate successful verification
                            state_data = StateData(
                                user_data={
                                    "document_id": "DEMO123",
                                    "name": "Usuario Demo",
                                    "employee_id": "DEMO001"
                                },
                                verification_result={
                                    "method": "demo",
                                    "confidence": 1.0
                                }
                            )
                            asyncio.create_task(
                                self.state_manager.transition_to(SystemState.CONFIRMATION, "demo_success", state_data)
                            )
                        elif event.key == pygame.K_F5:
                            asyncio.create_task(
                                self.state_manager.transition_to(SystemState.IDLE, "demo_return")
                            )
                    
                    # Let UI handle event
                    if self.ui_manager.current_screen:
                        self.ui_manager.current_screen.handle_event(event)
                
                if not self.running:
                    break
                
                # Update current screen
                if self.ui_manager.current_screen:
                    self.ui_manager.current_screen.update()
                
                # Clear screen
                self.ui_manager.screen.fill((245, 245, 245))  # UIColors.BACKGROUND
                
                # Draw current screen
                if self.ui_manager.current_screen:
                    self.ui_manager.current_screen.draw(self.ui_manager.screen)
                
                # Update display
                pygame.display.flip()
                clock.tick(30)  # 30 FPS
        
        except KeyboardInterrupt:
            self.logger.info("Demo interrupted by user")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up demo")
        self.running = False
        self.camera_manager.stop()
        self.ui_manager.stop()


if __name__ == "__main__":
    # Set environment variables for mock mode
    os.environ["MOCK_HARDWARE"] = "true"
    os.environ["DEBUG_MODE"] = "true"
    
    # Create and run demo
    demo = TerminalDemo()
    demo.run()