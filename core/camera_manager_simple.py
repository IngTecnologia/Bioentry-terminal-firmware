"""
Simplified Camera Manager for BioEntry Terminal
Based on the working logic from terminal_app.py - no mock code, just real camera.
"""

import cv2
import numpy as np
import os
import threading
import time
import queue
from typing import Optional, List, Tuple
from datetime import datetime
from picamera2 import Picamera2

from utils.config import get_config
from utils.logger import get_logger


class FaceDetector:
    """Face detection using OpenCV Haar Cascades - copied from terminal_app.py"""
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.face_cascade = self._load_face_cascade()
        
    def _load_face_cascade(self):
        """Load Haar cascade classifier"""
        cascade_paths = [
            '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
            '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
            '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
            'haarcascade_frontalface_default.xml'
        ]
        
        for path in cascade_paths:
            if os.path.exists(path):
                cascade = cv2.CascadeClassifier(path)
                if not cascade.empty():
                    self.logger.info(f"Face cascade loaded from: {path}")
                    return cascade
        
        raise Exception("Could not load face cascade classifier")
    
    def detect_faces(self, frame):
        """Detect faces in frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return faces
    
    def draw_faces(self, frame, faces):
        """Draw rectangles around detected faces - copied from terminal_app.py"""
        for (x, y, w, h) in faces:
            # Main green rectangle
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Semi-transparent interior rectangle
            overlay = frame.copy()
            cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 255, 0), -1)
            cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)
            
            # Large visible text
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


class SimpleCameraManager:
    """
    Simplified camera manager - only real camera, no mock code.
    Based on working logic from terminal_app.py
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Camera setup
        self.picam2 = Picamera2()
        self.face_detector = FaceDetector()
        
        # State
        self.is_running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Frame queue for UI
        self.frame_queue = queue.Queue(maxsize=2)
        
        # Setup camera - copied from terminal_app.py
        self.setup_camera()
        
        self.logger.info("Simple camera manager initialized")
    
    def setup_camera(self):
        """Setup camera with optimized resolution - copied from terminal_app.py"""
        config = self.picam2.create_preview_configuration(
            main={"size": (480, 640)}  # Vertical resolution for better quality
        )
        self.picam2.configure(config)
        self.logger.info("Camera configured: 480x640")
    
    def start(self):
        """Start camera and processing loop"""
        if self.is_running:
            return
        
        try:
            self.is_running = True
            
            # Start camera loop in background thread - copied from terminal_app.py
            camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            camera_thread.start()
            
            self.logger.info("Simple camera manager started")
            
        except Exception as e:
            self.logger.error(f"Failed to start camera: {str(e)}")
            self.is_running = False
    
    def stop(self):
        """Stop camera"""
        self.is_running = False
        try:
            if hasattr(self.picam2, 'stop'):
                self.picam2.stop()
        except:
            pass
        self.logger.info("Simple camera manager stopped")
    
    def _camera_loop(self):
        """Main camera loop - copied from terminal_app.py"""
        try:
            self.picam2.start()
            time.sleep(2)  # Let camera warm up
            
            self.logger.info("Camera loop started")
            
            while self.is_running:
                try:
                    # Capture frame
                    frame = self.picam2.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Detect faces
                    faces = self.face_detector.detect_faces(frame)
                    
                    # Draw detected faces
                    frame_with_faces = self.face_detector.draw_faces(frame, faces)
                    
                    # Store current frame
                    with self.frame_lock:
                        self.current_frame = frame_with_faces
                    
                    # Update UI frame queue
                    try:
                        if not self.frame_queue.full():
                            self.frame_queue.put(frame_with_faces, block=False)
                    except queue.Full:
                        pass
                    
                    # Log face detection
                    if len(faces) > 0:
                        self.logger.debug(f"Detected {len(faces)} face(s)")
                    
                    time.sleep(0.033)  # ~30 FPS
                    
                except Exception as e:
                    self.logger.error(f"Error in camera loop: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Critical camera loop error: {e}")
        finally:
            try:
                self.picam2.stop()
            except:
                pass
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current frame with face detection"""
        with self.frame_lock:
            if self.current_frame is not None:
                return self.current_frame.copy()
        return None
    
    def get_frame_from_queue(self) -> Optional[np.ndarray]:
        """Get frame from queue (for UI updates)"""
        try:
            return self.frame_queue.get(timeout=0.1)
        except queue.Empty:
            return None


# Global instance
_camera_manager = None

def get_simple_camera_manager() -> SimpleCameraManager:
    """Get global camera manager instance"""
    global _camera_manager
    if _camera_manager is None:
        _camera_manager = SimpleCameraManager()
    return _camera_manager