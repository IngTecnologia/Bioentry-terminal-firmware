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


class CameraManager:
    """Camera manager with Picamera2 support and mock fallback"""
    
    def __init__(self):
        self.running = False
        self.frame_callback = None
        self.face_callback = None
        self.use_picamera = False
        self.picam2 = None
        self.face_detector = None
        
        # Try to initialize Picamera2 and face detector
        self._initialize_camera()
        self._initialize_face_detector()
        
    def _initialize_camera(self):
        """Initialize Picamera2 if available"""
        try:
            from picamera2 import Picamera2
            self.picam2 = Picamera2()
            # Configure for 480x800 display (vertical orientation)
            config = self.picam2.create_preview_configuration(
                main={"size": (640, 480)}  # Standard resolution
            )
            self.picam2.configure(config)
            self.use_picamera = True
            print("Picamera2 initialized successfully")
        except ImportError:
            print("Picamera2 not available, using mock camera")
            self.use_picamera = False
        except Exception as e:
            print(f"Error initializing Picamera2: {e}, using mock camera")
            self.use_picamera = False
    
    def _initialize_face_detector(self):
        """Initialize face detector with OpenCV"""
        try:
            import cv2
            
            # Try to load face cascade from common paths
            cascade_paths = [
                '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
                '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
                '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
                'haarcascade_frontalface_default.xml'
            ]
            
            for path in cascade_paths:
                if os.path.exists(path):
                    self.face_detector = cv2.CascadeClassifier(path)
                    if not self.face_detector.empty():
                        print(f"Face detector loaded from: {path}")
                        break
            
            if self.face_detector is None or self.face_detector.empty():
                print("Face detector not available, using mock detection")
                self.face_detector = None
                
        except ImportError:
            print("OpenCV not available, using mock face detection")
            self.face_detector = None
        
    def start(self, frame_callback=None, face_callback=None):
        """Start camera"""
        self.running = True
        self.frame_callback = frame_callback
        self.face_callback = face_callback
        
        if self.use_picamera:
            # Start real camera
            threading.Thread(target=self._real_camera_loop, daemon=True).start()
        else:
            # Start mock camera
            threading.Thread(target=self._mock_camera_loop, daemon=True).start()
    
    def stop(self):
        """Stop camera"""
        self.running = False
        if self.use_picamera and self.picam2:
            try:
                self.picam2.stop()
            except:
                pass
    
    def _real_camera_loop(self):
        """Real camera loop using Picamera2"""
        try:
            self.picam2.start()
            time.sleep(2)  # Allow camera to warm up
            
            while self.running:
                try:
                    # Capture frame
                    frame = self.picam2.capture_array()
                    
                    # Convert RGB to BGR for OpenCV compatibility
                    import cv2
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Detect faces if detector is available
                    faces = []
                    if self.face_detector is not None:
                        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                        faces = self.face_detector.detectMultiScale(
                            gray,
                            scaleFactor=1.1,
                            minNeighbors=5,
                            minSize=(50, 50)
                        )
                        
                        # Draw face rectangles
                        for (x, y, w, h) in faces:
                            cv2.rectangle(frame_bgr, (x, y), (x+w, y+h), (0, 255, 0), 2)
                            cv2.putText(frame_bgr, "FACE DETECTED", (x, y-10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
                    # Send frame to callback
                    if self.frame_callback:
                        self.frame_callback(frame_bgr)
                    
                    # Send face detections
                    if self.face_callback and len(faces) > 0:
                        # Normalize coordinates
                        height, width = frame_bgr.shape[:2]
                        normalized_faces = []
                        for (x, y, w, h) in faces:
                            normalized_faces.append((x/width, y/height, w/width, h/height))
                        self.face_callback(normalized_faces)
                    
                    time.sleep(1/15)  # 15 FPS
                    
                except Exception as e:
                    print(f"Error in real camera loop: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Critical error in real camera: {e}")
            # Fall back to mock camera
            self._mock_camera_loop()
    
    def _mock_camera_loop(self):
        """Mock camera loop for demonstration"""
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
                try:
                    import cv2
                    cv2.rectangle(frame, (250, 180), (390, 300), (0, 255, 0), 3)
                    cv2.putText(frame, "MOCK FACE", (270, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                except ImportError:
                    pass
                
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
        
        # Initialize services
        self.camera_manager = CameraManager()
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