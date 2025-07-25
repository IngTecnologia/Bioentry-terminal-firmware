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
        
        # Performance monitoring
        self.last_performance_check = time.time()
        self.frame_processing_times = []
        self.adaptive_fps = 30
        self.target_processing_time = 0.033  # 30 FPS target
        
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
        """Main camera loop with improved error handling and recovery"""
        consecutive_errors = 0
        max_consecutive_errors = 5
        last_frame_time = time.time()
        
        try:
            self.picam2.start()
            time.sleep(2)  # Let camera warm up
            
            self.logger.info("Camera loop started")
            
            while self.is_running:
                try:
                    current_time = time.time()
                    
                    # Check for camera timeout (no frames for 5 seconds)
                    if current_time - last_frame_time > 5.0:
                        self.logger.warning("Camera timeout detected, attempting recovery")
                        self._attempt_camera_recovery()
                        last_frame_time = current_time
                        continue
                    
                    # Performance monitoring start
                    processing_start = time.time()
                    
                    # Capture frame with timeout
                    frame = self.picam2.capture_array()
                    if frame is None:
                        raise Exception("Camera returned None frame")
                    
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    last_frame_time = current_time
                    
                    # Adaptive face detection (skip some frames if system is slow)
                    faces = []
                    if len(self.frame_processing_times) == 0 or self.frame_processing_times[-1] < self.target_processing_time * 1.5:
                        faces = self.face_detector.detect_faces(frame)
                    
                    # Draw detected faces
                    frame_with_faces = self.face_detector.draw_faces(frame, faces)
                    
                    # Performance monitoring end
                    processing_time = time.time() - processing_start
                    self.frame_processing_times.append(processing_time)
                    
                    # Keep only last 30 measurements
                    if len(self.frame_processing_times) > 30:
                        self.frame_processing_times.pop(0)
                    
                    # Adaptive FPS based on processing time
                    if len(self.frame_processing_times) >= 10:
                        avg_processing_time = sum(self.frame_processing_times[-10:]) / 10
                        if avg_processing_time > self.target_processing_time * 1.2:
                            # System is struggling, reduce FPS
                            self.adaptive_fps = max(15, self.adaptive_fps - 1)
                        elif avg_processing_time < self.target_processing_time * 0.8:
                            # System is doing well, can increase FPS
                            self.adaptive_fps = min(30, self.adaptive_fps + 1)
                    
                    # Store current frame
                    with self.frame_lock:
                        self.current_frame = frame_with_faces
                    
                    # Update UI frame queue
                    try:
                        if not self.frame_queue.full():
                            self.frame_queue.put(frame_with_faces, block=False)
                    except queue.Full:
                        # Clear old frames if queue is full
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put(frame_with_faces, block=False)
                        except queue.Empty:
                            pass
                    
                    # Log face detection
                    if len(faces) > 0:
                        self.logger.debug(f"Detected {len(faces)} face(s)")
                    
                    # Reset error counter on successful frame
                    consecutive_errors = 0
                    
                    # Adaptive sleep based on measured performance
                    sleep_time = max(0.01, 1.0 / self.adaptive_fps - processing_time)
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    consecutive_errors += 1
                    self.logger.error(f"Error in camera loop (#{consecutive_errors}): {e}")
                    
                    # Progressive backoff for consecutive errors
                    if consecutive_errors >= max_consecutive_errors:
                        self.logger.error("Too many consecutive camera errors, attempting full recovery")
                        if not self._attempt_camera_recovery():
                            self.logger.error("Camera recovery failed, stopping camera loop")
                            break
                        consecutive_errors = 0
                        
                        # Log performance stats periodically
                        if current_time - self.last_performance_check > 10.0:  # Every 10 seconds
                            self._log_performance_stats()
                            self.last_performance_check = current_time
                    else:
                        # Short delay before retry
                        time.sleep(min(consecutive_errors * 0.5, 2.0))
                    
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
    
    def _attempt_camera_recovery(self) -> bool:
        """Attempt to recover from camera errors"""
        try:
            self.logger.info("Attempting camera recovery...")
            
            # Stop current camera
            try:
                self.picam2.stop()
                time.sleep(1)
            except:
                pass
            
            # Reinitialize camera
            try:
                self.setup_camera()
                self.picam2.start()
                time.sleep(2)
                
                # Test with a frame capture
                test_frame = self.picam2.capture_array()
                if test_frame is not None:
                    self.logger.info("Camera recovery successful")
                    return True
                else:
                    self.logger.error("Camera recovery failed - test frame is None")
                    return False
                    
            except Exception as e:
                self.logger.error(f"Camera recovery failed: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Critical error during camera recovery: {e}")
            return False
    
    def _log_performance_stats(self):
        """Log camera performance statistics"""
        try:
            if len(self.frame_processing_times) > 0:
                avg_time = sum(self.frame_processing_times) / len(self.frame_processing_times)
                max_time = max(self.frame_processing_times)
                min_time = min(self.frame_processing_times)
                
                self.logger.info(
                    f"Camera performance: avg={avg_time:.3f}s, max={max_time:.3f}s, "
                    f"min={min_time:.3f}s, adaptive_fps={self.adaptive_fps}"
                )
            
            # Check system temperature if available (Raspberry Pi)
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp_millidegrees = int(f.read().strip())
                    temp_celsius = temp_millidegrees / 1000.0
                    
                    if temp_celsius > 70.0:  # High temperature warning
                        self.logger.warning(f"High system temperature: {temp_celsius:.1f}°C")
                        # Reduce FPS to lower CPU load
                        self.adaptive_fps = max(10, self.adaptive_fps - 5)
                    elif temp_celsius > 80.0:  # Critical temperature
                        self.logger.error(f"Critical system temperature: {temp_celsius:.1f}°C")
                        self.adaptive_fps = 10  # Minimum FPS
                    else:
                        self.logger.debug(f"System temperature: {temp_celsius:.1f}°C")
                        
            except (FileNotFoundError, ValueError):
                # Temperature monitoring not available
                pass
                
        except Exception as e:
            self.logger.error(f"Error logging performance stats: {e}")
    
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