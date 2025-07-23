"""
Camera Manager for BioEntry Terminal
Handles camera operations for facial recognition and image capture.
"""

import cv2
import numpy as np
import os
import threading
import time
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
import asyncio

from utils.config import get_config
from utils.logger import get_logger


class CameraManager:
    """
    Camera manager for facial recognition and image capture.
    
    Supports both real hardware (Picamera2 on Raspberry Pi) and mock mode for development.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Camera configuration
        self.resolution = self.config.hardware.camera_resolution
        self.fps = self.config.hardware.camera_fps
        self.rotation = self.config.hardware.camera_rotation
        
        # Camera state
        self.camera = None
        self.is_initialized = False
        self.is_recording = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Mock mode detection
        self.mock_mode = self.config.is_mock_mode() or not self.config.hardware.camera_enabled
        
        # Performance tracking
        self.frame_count = 0
        self.last_fps_check = time.time()
        self.actual_fps = 0.0
        
        self.logger.info(f"Camera manager initialized - Mock mode: {self.mock_mode}")
    
    async def initialize(self) -> bool:
        """
        Initialize camera hardware or mock camera.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            if self.mock_mode:
                return await self._initialize_mock_camera()
            else:
                return await self._initialize_real_camera()
        except Exception as e:
            self.logger.error(f"Camera initialization failed: {str(e)}")
            return False
    
    async def _initialize_real_camera(self) -> bool:
        """Initialize real camera hardware (Picamera2)."""
        try:
            # Try to import Picamera2 (Raspberry Pi)
            from picamera2 import Picamera2
            
            self.camera = Picamera2()
            
            # Configure camera
            config = self.camera.create_still_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self.camera.configure(config)
            
            # Start camera
            self.camera.start()
            
            # Wait for camera to warm up
            await asyncio.sleep(2)
            
            self.is_initialized = True
            self.logger.info(f"Real camera initialized: {self.resolution}@{self.fps}fps")
            return True
            
        except ImportError:
            self.logger.warning("Picamera2 not available, falling back to OpenCV")
            return await self._initialize_opencv_camera()
        except Exception as e:
            self.logger.error(f"Real camera initialization failed: {str(e)}")
            return False
    
    async def _initialize_opencv_camera(self) -> bool:
        """Initialize OpenCV camera (USB camera fallback)."""
        try:
            self.camera = cv2.VideoCapture(0)
            
            if not self.camera.isOpened():
                raise Exception("Cannot open camera")
            
            # Set camera properties
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera.set(cv2.CAP_PROP_FPS, self.fps)
            
            self.is_initialized = True
            self.logger.info(f"OpenCV camera initialized: {self.resolution}@{self.fps}fps")
            return True
            
        except Exception as e:
            self.logger.error(f"OpenCV camera initialization failed: {str(e)}")
            return False
    
    async def _initialize_mock_camera(self) -> bool:
        """Initialize mock camera for development."""
        try:
            # Create mock camera state
            self.camera = "mock_camera"
            self.is_initialized = True
            
            # Generate initial mock frame
            self.current_frame = self._generate_mock_frame()
            
            self.logger.info(f"Mock camera initialized: {self.resolution}@{self.fps}fps")
            return True
            
        except Exception as e:
            self.logger.error(f"Mock camera initialization failed: {str(e)}")
            return False
    
    def _generate_mock_frame(self) -> np.ndarray:
        """
        Generate a mock camera frame for development.
        
        Returns:
            Mock frame as numpy array
        """
        width, height = self.resolution
        
        # Create base frame with gradient background
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Add gradient background
        for y in range(height):
            intensity = int((y / height) * 100 + 50)
            frame[y, :] = [intensity, intensity // 2, intensity // 3]
        
        # Add mock face rectangle
        face_width = width // 3
        face_height = height // 3
        face_x = (width - face_width) // 2
        face_y = (height - face_height) // 2
        
        # Draw face rectangle
        cv2.rectangle(frame, (face_x, face_y), (face_x + face_width, face_y + face_height), (100, 150, 200), 2)
        
        # Add text overlay
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, f"MOCK CAMERA {timestamp}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Resolution: {width}x{height}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        # Add simulated noise
        noise = np.random.randint(0, 20, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)
        
        return frame
    
    async def start_preview(self) -> bool:
        """
        Start camera preview/streaming.
        
        Returns:
            True if started successfully, False otherwise
        """
        if not self.is_initialized:
            if not await self.initialize():
                return False
        
        if self.is_recording:
            return True
        
        try:
            self.is_recording = True
            
            if self.mock_mode:
                # Start mock preview loop in background
                asyncio.create_task(self._mock_preview_loop())
            else:
                # Start real camera preview loop in background
                asyncio.create_task(self._real_preview_loop())
            
            self.logger.info("Camera preview started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start camera preview: {str(e)}")
            self.is_recording = False
            return False
    
    async def _mock_preview_loop(self):
        """Background loop for mock camera frames."""
        while self.is_recording:
            try:
                # Generate new mock frame
                new_frame = self._generate_mock_frame()
                
                with self.frame_lock:
                    self.current_frame = new_frame
                
                # Update FPS tracking
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_check >= 1.0:
                    self.actual_fps = self.frame_count / (current_time - self.last_fps_check)
                    self.frame_count = 0
                    self.last_fps_check = current_time
                
                # Sleep to maintain target FPS
                await asyncio.sleep(1.0 / self.fps)
                
            except Exception as e:
                self.logger.error(f"Mock preview loop error: {str(e)}")
                break
    
    async def _real_preview_loop(self):
        """Background loop for real camera frames."""
        self.logger.info("Starting real camera preview loop")
        try:
            # Camera should already be started from initialize()
            if not self.camera:
                self.logger.error("Camera not available")
                return
            
            self.logger.info(f"Real camera preview loop ready with camera: {type(self.camera)}")
            
            while self.is_recording:
                try:
                    # Capture frame from real camera
                    if self.camera and hasattr(self.camera, 'capture_array'):
                        frame = self.camera.capture_array()
                        
                        # Convert RGB to BGR for consistency with capture_frame
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                        
                        # Convert BGR to RGB (final output format)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # Detect faces in the frame
                        try:
                            faces = self.detect_faces(frame)
                            if faces:
                                # Draw face detection boxes on the frame
                                frame = self._draw_face_boxes(frame, faces)
                                
                                # Log face detection
                                if not hasattr(self, '_face_detected_logged'):
                                    self.logger.info(f"Face detection working: {len(faces)} faces detected")
                                    self._face_detected_logged = True
                        except Exception as e:
                            self.logger.error(f"Face detection error: {str(e)}")
                        
                        with self.frame_lock:
                            self.current_frame = frame
                        
                        # Log first frame capture
                        if not hasattr(self, '_first_frame_logged'):
                            self.logger.info(f"First real camera frame captured: {frame.shape}")
                            self._first_frame_logged = True
                    else:
                        self.logger.error(f"Cannot capture array from camera: {self.camera}")
                    
                    # Update FPS tracking
                    self.frame_count += 1
                    current_time = time.time()
                    if current_time - self.last_fps_check >= 1.0:
                        self.actual_fps = self.frame_count / (current_time - self.last_fps_check)
                        self.frame_count = 0
                        self.last_fps_check = current_time
                    
                    # Sleep to maintain target FPS
                    await asyncio.sleep(1.0 / self.fps)
                    
                except Exception as e:
                    self.logger.error(f"Error capturing real camera frame: {str(e)}")
                    await asyncio.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Error in real preview loop: {str(e)}")
        finally:
            # Stop camera when loop ends
            if self.camera and hasattr(self.camera, 'stop'):
                try:
                    self.camera.stop()
                except:
                    pass
    
    def stop_preview(self) -> None:
        """Stop camera preview/streaming."""
        self.is_recording = False
        self.logger.info("Camera preview stopped")
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from the camera.
        
        Returns:
            Frame as numpy array, or None if capture failed
        """
        if not self.is_initialized:
            self.logger.warning("Camera not initialized")
            return None
        
        try:
            if self.mock_mode:
                return self._capture_mock_frame()
            elif hasattr(self.camera, 'capture_array'):  # Picamera2
                return self._capture_picamera_frame()
            else:  # OpenCV
                return self._capture_opencv_frame()
                
        except Exception as e:
            self.logger.error(f"Frame capture failed: {str(e)}")
            return None
    
    def _capture_mock_frame(self) -> np.ndarray:
        """Capture frame from mock camera."""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
            else:
                return self._generate_mock_frame()
    
    def _capture_picamera_frame(self) -> np.ndarray:
        """Capture frame from Picamera2."""
        frame = self.camera.capture_array()
        
        # Apply rotation if configured
        if self.rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        return frame
    
    def _capture_opencv_frame(self) -> Optional[np.ndarray]:
        """Capture frame from OpenCV camera."""
        ret, frame = self.camera.read()
        if not ret:
            return None
        
        # Convert BGR to RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Apply rotation if configured
        if self.rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        
        return frame
    
    def capture_image(self) -> Optional[bytes]:
        """
        Capture image as JPEG bytes for API submission.
        
        Returns:
            Image as JPEG bytes, or None if capture failed
        """
        frame = self.capture_frame()
        if frame is None:
            return None
        
        try:
            # Convert to BGR for OpenCV encoding
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                frame_bgr = frame
            
            # Encode as JPEG
            success, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            if success:
                return buffer.tobytes()
            else:
                self.logger.error("Failed to encode image as JPEG")
                return None
                
        except Exception as e:
            self.logger.error(f"Image encoding failed: {str(e)}")
            return None
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """
        Get the current frame from preview stream.
        
        Returns:
            Current frame as numpy array, or None if not available
        """
        if not self.is_recording:
            return self.capture_frame()
        
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        
        return None
    
    def detect_faces(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """
        Detect faces in the given frame or current frame.
        
        Args:
            frame: Optional frame to analyze, uses current frame if None
            
        Returns:
            List of detected faces with bounding boxes and confidence
        """
        if frame is None:
            frame = self.get_current_frame()
        
        if frame is None:
            return []
        
        try:
            if self.mock_mode:
                return self._mock_face_detection(frame)
            else:
                return self._real_face_detection(frame)
                
        except Exception as e:
            self.logger.error(f"Face detection failed: {str(e)}")
            return []
    
    def _mock_face_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Mock face detection for development."""
        height, width = frame.shape[:2]
        
        # Return mock face detection
        face_width = width // 3
        face_height = height // 3
        face_x = (width - face_width) // 2
        face_y = (height - face_height) // 2
        
        return [{
            'x': face_x,
            'y': face_y,
            'width': face_width,
            'height': face_height,
            'confidence': 0.95
        }]
    
    def _real_face_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Real face detection using OpenCV."""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        
        # Load face cascade (should be available in OpenCV)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        # Convert to list of dictionaries
        detected_faces = []
        for (x, y, w, h) in faces:
            detected_faces.append({
                'x': int(x),
                'y': int(y),
                'width': int(w),
                'height': int(h),
                'confidence': 0.8  # OpenCV doesn't provide confidence, use default
            })
        
        return detected_faces
    
    def _draw_face_boxes(self, frame: np.ndarray, faces: List[Dict[str, Any]]) -> np.ndarray:
        """Draw face detection boxes on frame, similar to terminal_app.py"""
        for face in faces:
            # Extract bounding box coordinates
            x, y, w, h = int(face['x']), int(face['y']), int(face['width']), int(face['height'])
            
            # Main green rectangle
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Semi-transparent overlay
            overlay = frame.copy()
            cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 255, 0), -1)
            cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)
            
            # Text label
            font_scale = 1.0
            thickness = 2
            text = 'CARA DETECTADA'
            
            # Calculate centered text position
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            text_x = x + (w - text_size[0]) // 2
            text_y = y - 15 if y > 30 else y + h + 25
            
            # Text background
            cv2.rectangle(frame, (text_x - 5, text_y - text_size[1] - 5), 
                         (text_x + text_size[0] + 5, text_y + 5), (0, 0, 0), -1)
            
            # Text
            cv2.putText(frame, text, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)
            
            # Focus corners
            corner_length = 20
            corner_thickness = 4
            
            # Top-left corner
            cv2.line(frame, (x, y), (x + corner_length, y), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x, y), (x, y + corner_length), (0, 255, 0), corner_thickness)
            
            # Top-right corner
            cv2.line(frame, (x + w, y), (x + w - corner_length, y), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x + w, y), (x + w, y + corner_length), (0, 255, 0), corner_thickness)
            
            # Bottom-left corner
            cv2.line(frame, (x, y + h), (x + corner_length, y + h), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x, y + h), (x, y + h - corner_length), (0, 255, 0), corner_thickness)
            
            # Bottom-right corner
            cv2.line(frame, (x + w, y + h), (x + w - corner_length, y + h), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x + w, y + h), (x + w, y + h - corner_length), (0, 255, 0), corner_thickness)
        
        return frame
    
    def get_camera_info(self) -> Dict[str, Any]:
        """
        Get camera information and status.
        
        Returns:
            Dictionary with camera information
        """
        return {
            'initialized': self.is_initialized,
            'recording': self.is_recording,
            'mock_mode': self.mock_mode,
            'resolution': self.resolution,
            'target_fps': self.fps,
            'actual_fps': self.actual_fps,
            'rotation': self.rotation,
            'frame_count': self.frame_count
        }
    
    def cleanup(self) -> None:
        """Clean up camera resources."""
        try:
            self.stop_preview()
            
            if self.camera and not self.mock_mode:
                if hasattr(self.camera, 'stop'):  # Picamera2
                    self.camera.stop()
                elif hasattr(self.camera, 'release'):  # OpenCV
                    self.camera.release()
            
            self.is_initialized = False
            self.camera = None
            
            self.logger.info("Camera cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Camera cleanup error: {str(e)}")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()


# Global camera manager instance
_camera_manager = None


def get_camera_manager() -> CameraManager:
    """Get the global camera manager instance."""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = CameraManager()
    return _camera_manager


if __name__ == "__main__":
    # Test camera manager
    import asyncio
    
    async def test_camera_manager():
        camera = get_camera_manager()
        
        print("Testing camera manager...")
        print(f"Camera info: {camera.get_camera_info()}")
        
        # Initialize camera
        if await camera.initialize():
            print("Camera initialized successfully")
            
            # Start preview
            if await camera.start_preview():
                print("Camera preview started")
                
                # Capture some frames
                for i in range(5):
                    frame = camera.capture_frame()
                    if frame is not None:
                        print(f"Captured frame {i+1}: {frame.shape}")
                    
                    # Test face detection
                    faces = camera.detect_faces(frame)
                    print(f"Detected {len(faces)} faces")
                    
                    await asyncio.sleep(1)
                
                # Test image capture
                image_bytes = camera.capture_image()
                if image_bytes:
                    print(f"Captured image: {len(image_bytes)} bytes")
                
                camera.stop_preview()
                print("Camera preview stopped")
            
            camera.cleanup()
            print("Camera cleaned up")
        else:
            print("Camera initialization failed")
    
    asyncio.run(test_camera_manager())