"""
Comprehensive Verification Service for BioEntry Terminal
Orchestrates all verification methods: facial (online), fingerprint (offline), and manual entry.

IMPORTANT: This service integrates API-based facial recognition with local fingerprint verification.
It handles the complete verification workflow including fallback mechanisms.
"""

import asyncio
import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
import uuid
import io

from services.api_client import get_api_client, VerificationResult
from core.database_manager import get_database_manager
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager, SystemState, StateData


@dataclass
class VerificationRequest:
    """Unified verification request structure"""
    method: str  # 'facial', 'fingerprint', 'manual'
    image_data: Optional[bytes] = None
    cedula: Optional[str] = None
    fingerprint_template: Optional[bytes] = None
    location: Optional[Tuple[float, float]] = None  # (lat, lng)
    forced_type: Optional[str] = None  # 'entrada' or 'salida' - override auto-detection


@dataclass
class VerificationResponse:
    """Unified verification response structure"""
    success: bool
    verified: bool
    user_data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    method_used: str = 'unknown'
    verification_type: str = 'entrada'  # 'entrada' or 'salida'
    record_id: Optional[str] = None
    error_message: Optional[str] = None
    fallback_available: bool = False
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class VerificationService:
    """
    Complete verification service for BioEntry terminal.
    
    This service orchestrates all verification methods:
    - Online facial recognition via API
    - Offline fingerprint verification via AS608 sensor
    - Manual document ID entry as fallback
    - Automatic fallback between methods based on connectivity and configuration
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.db_manager = get_database_manager()
        self.api_client = get_api_client()
        self.state_manager = get_state_manager()
        
        # Verification configuration
        self.max_facial_attempts = self.config.operation.max_facial_attempts
        self.max_fingerprint_attempts = self.config.operation.max_fingerprint_attempts
        self.verification_timeout = self.config.operation.verification_timeout_seconds
        
        # Current verification state
        self.current_verification = None
        self.verification_attempts = {}  # Track attempts per method
        
        self.logger.info("Verification service initialized")
    
    # ==========================================
    # MAIN VERIFICATION ORCHESTRATION
    # ==========================================
    
    async def verify_user(self, request: VerificationRequest) -> VerificationResponse:
        """
        Main verification method that orchestrates all verification types.
        
        Args:
            request: VerificationRequest with method and data
        
        Returns:
            VerificationResponse with results
        """
        self.logger.info(f"Starting verification with method: {request.method}")
        
        # Initialize verification tracking
        verification_id = str(uuid.uuid4())
        self.current_verification = {
            'id': verification_id,
            'started_at': datetime.utcnow(),
            'method': request.method,
            'attempts': 0
        }
        
        try:
            # Route to appropriate verification method
            if request.method == 'facial':
                return await self._verify_facial(request)
            elif request.method == 'fingerprint':
                return await self._verify_fingerprint(request)
            elif request.method == 'manual':
                return await self._verify_manual(request)
            else:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message=f"Unsupported verification method: {request.method}"
                )
        
        except Exception as e:
            self.logger.error(f"Verification failed with error: {str(e)}")
            return VerificationResponse(
                success=False,
                verified=False,
                error_message=f"Verification error: {str(e)}",
                method_used=request.method
            )
        
        finally:
            self.current_verification = None
    
    async def verify_with_fallback(self, primary_request: VerificationRequest) -> VerificationResponse:
        """
        Verify with automatic fallback to alternative methods.
        
        Args:
            primary_request: Primary verification request
        
        Returns:
            VerificationResponse with results from primary or fallback method
        """
        self.logger.info(f"Starting verification with fallback, primary method: {primary_request.method}")
        
        # Try primary method first
        primary_response = await self.verify_user(primary_request)
        
        if primary_response.success and primary_response.verified:
            return primary_response
        
        # Determine fallback strategy based on configuration and connectivity
        fallback_methods = self._get_fallback_methods(primary_request.method)
        
        for fallback_method in fallback_methods:
            self.logger.info(f"Attempting fallback to: {fallback_method}")
            
            try:
                # Create fallback request
                fallback_request = VerificationRequest(
                    method=fallback_method,
                    location=primary_request.location,
                    forced_type=primary_request.forced_type
                )
                
                # For manual fallback, we don't need image data
                if fallback_method != 'manual':
                    fallback_request.image_data = primary_request.image_data
                
                fallback_response = await self.verify_user(fallback_request)
                
                if fallback_response.success and fallback_response.verified:
                    # Mark as fallback in response
                    fallback_response.method_used = f"{primary_request.method}_to_{fallback_method}"
                    return fallback_response
                
            except Exception as e:
                self.logger.error(f"Fallback method {fallback_method} failed: {str(e)}")
                continue
        
        # All methods failed
        return VerificationResponse(
            success=False,
            verified=False,
            error_message="All verification methods failed",
            method_used=primary_request.method,
            fallback_available=len(fallback_methods) > 0
        )
    
    def _get_fallback_methods(self, primary_method: str) -> List[str]:
        """
        Determine available fallback methods based on primary method and system state.
        
        Args:
            primary_method: The primary method that failed
        
        Returns:
            List of fallback methods to try
        """
        fallback_methods = []
        
        # Check connectivity for online methods
        is_online = self.api_client.is_online
        
        if primary_method == 'facial':
            if self.config.hardware.fingerprint_enabled:
                fallback_methods.append('fingerprint')
            fallback_methods.append('manual')
        
        elif primary_method == 'fingerprint':
            if is_online and self.config.hardware.camera_enabled:
                fallback_methods.append('facial')
            fallback_methods.append('manual')
        
        elif primary_method == 'manual':
            # Manual is typically the final fallback
            if is_online and self.config.hardware.camera_enabled:
                fallback_methods.append('facial')
            if self.config.hardware.fingerprint_enabled:
                fallback_methods.append('fingerprint')
        
        return fallback_methods
    
    # ==========================================
    # FACIAL VERIFICATION (ONLINE)
    # ==========================================
    
    async def _verify_facial(self, request: VerificationRequest) -> VerificationResponse:
        """
        Perform facial verification using API.
        
        Args:
            request: VerificationRequest with image data
        
        Returns:
            VerificationResponse with results
        """
        if not request.image_data:
            return VerificationResponse(
                success=False,
                verified=False,
                error_message="No image data provided for facial verification",
                method_used='facial'
            )
        
        # Check connectivity
        if not await self.api_client.check_connectivity():
            return VerificationResponse(
                success=False,
                verified=False,
                error_message="Cannot perform facial verification - terminal is offline",
                method_used='facial',
                fallback_available=True
            )
        
        try:
            # Extract location if provided
            lat, lng = request.location if request.location else (None, None)
            
            # Use automatic verification (identifies user and detects entry/exit type)
            api_response = await self.api_client.verify_face_automatic(
                image_bytes=request.image_data,
                lat=lat,
                lng=lng
            )
            
            if not api_response.success:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message=api_response.error,
                    method_used='facial',
                    fallback_available=True
                )
            
            # Parse API response
            verification_result = self.api_client.parse_verification_result(api_response)
            
            if not verification_result:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message="Failed to parse verification result",
                    method_used='facial'
                )
            
            # Create response based on API result
            response = VerificationResponse(
                success=True,
                verified=verification_result.verified,
                user_data={
                    'cedula': verification_result.cedula,
                    'nombre': verification_result.nombre,
                    'ubicacion': verification_result.ubicacion
                },
                confidence=1.0 - verification_result.distance,  # Convert distance to confidence
                method_used='facial',
                verification_type=verification_result.tipo_registro,
                record_id=verification_result.record_id
            )
            
            # Save local record if verification succeeded
            if verification_result.verified:
                await self._save_local_record(response, request)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Facial verification error: {str(e)}")
            return VerificationResponse(
                success=False,
                verified=False,
                error_message=f"Facial verification failed: {str(e)}",
                method_used='facial',
                fallback_available=True
            )
    
    # ==========================================
    # FINGERPRINT VERIFICATION (OFFLINE)
    # ==========================================
    
    async def _verify_fingerprint(self, request: VerificationRequest) -> VerificationResponse:
        """
        Perform fingerprint verification using AS608 sensor.
        
        Args:
            request: VerificationRequest (image_data not used for fingerprint)
        
        Returns:
            VerificationResponse with results
        """
        try:
            # Import fingerprint manager
            from core.fingerprint_manager import get_fingerprint_manager
            fingerprint_manager = get_fingerprint_manager()
            
            if not fingerprint_manager.is_available():
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message="Fingerprint sensor not available",
                    method_used='fingerprint',
                    fallback_available=True
                )
            
            # Perform fingerprint verification
            # This will prompt user to place finger and verify against stored templates
            fingerprint_result = await fingerprint_manager.verify_fingerprint()
            
            if not fingerprint_result['success']:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message=fingerprint_result.get('error', 'Fingerprint verification failed'),
                    method_used='fingerprint',
                    fallback_available=True
                )
            
            # Get user data from local database using template ID
            template_id = fingerprint_result.get('template_id')
            confidence = fingerprint_result.get('confidence', 0.0)
            
            user_data = await self.db_manager.get_user_by_fingerprint_template(template_id)
            
            if not user_data:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message="User not found for fingerprint template",
                    method_used='fingerprint'
                )
            
            # Determine entry/exit type
            verification_type = await self._detect_entry_exit_type(user_data['cedula'])
            if request.forced_type:
                verification_type = request.forced_type
            
            # Create successful response
            response = VerificationResponse(
                success=True,
                verified=True,
                user_data=user_data,
                confidence=confidence,
                method_used='fingerprint',
                verification_type=verification_type,
                record_id=str(uuid.uuid4())
            )
            
            # Save local record
            await self._save_local_record(response, request)
            
            return response
            
        except ImportError:
            # Fingerprint manager not available (mock mode or missing hardware)
            return await self._mock_fingerprint_verification(request)
        
        except Exception as e:
            self.logger.error(f"Fingerprint verification error: {str(e)}")
            return VerificationResponse(
                success=False,
                verified=False,
                error_message=f"Fingerprint verification failed: {str(e)}",
                method_used='fingerprint',
                fallback_available=True
            )
    
    async def _mock_fingerprint_verification(self, request: VerificationRequest) -> VerificationResponse:
        """Mock fingerprint verification for testing/development"""
        self.logger.info("Using mock fingerprint verification")
        
        # Simulate fingerprint reading delay
        await asyncio.sleep(2)
        
        # Get a random user from database for testing
        users = await self.db_manager.get_all_users()
        if not users:
            return VerificationResponse(
                success=False,
                verified=False,
                error_message="No users in database for mock verification",
                method_used='fingerprint'
            )
        
        # Use first user for mock verification
        user_data = users[0]
        verification_type = await self._detect_entry_exit_type(user_data['cedula'])
        
        response = VerificationResponse(
            success=True,
            verified=True,
            user_data=user_data,
            confidence=0.95,  # Mock confidence
            method_used='fingerprint',
            verification_type=verification_type,
            record_id=str(uuid.uuid4())
        )
        
        # Save local record
        await self._save_local_record(response, request)
        
        return response
    
    # ==========================================
    # MANUAL VERIFICATION (FALLBACK)
    # ==========================================
    
    async def _verify_manual(self, request: VerificationRequest) -> VerificationResponse:
        """
        Perform manual verification using document ID.
        This method requires user interaction and is typically handled by the UI.
        
        Args:
            request: VerificationRequest with cedula
        
        Returns:
            VerificationResponse with results
        """
        if not request.cedula:
            return VerificationResponse(
                success=False,
                verified=False,
                error_message="No document ID provided for manual verification",
                method_used='manual'
            )
        
        try:
            # Validate document ID format
            if not self._validate_cedula(request.cedula):
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message="Invalid document ID format",
                    method_used='manual'
                )
            
            # Look up user in local database
            user_data = await self.db_manager.get_user_by_cedula(request.cedula)
            
            if not user_data:
                return VerificationResponse(
                    success=False,
                    verified=False,
                    error_message="User not found in local database",
                    method_used='manual'
                )
            
            # Determine entry/exit type
            verification_type = await self._detect_entry_exit_type(request.cedula)
            if request.forced_type:
                verification_type = request.forced_type
            
            # Create successful response
            response = VerificationResponse(
                success=True,
                verified=True,
                user_data=user_data,
                confidence=1.0,  # Manual entry is considered 100% confident
                method_used='manual',
                verification_type=verification_type,
                record_id=str(uuid.uuid4())
            )
            
            # Save local record
            await self._save_local_record(response, request)
            
            return response
            
        except Exception as e:
            self.logger.error(f"Manual verification error: {str(e)}")
            return VerificationResponse(
                success=False,
                verified=False,
                error_message=f"Manual verification failed: {str(e)}",
                method_used='manual'
            )
    
    # ==========================================
    # UTILITY METHODS
    # ==========================================
    
    async def _detect_entry_exit_type(self, cedula: str) -> str:
        """
        Detect if this should be an entry or exit record based on last record.
        
        Args:
            cedula: User's document ID
        
        Returns:
            'entrada' or 'salida'
        """
        try:
            last_record = await self.db_manager.get_last_record_by_user(cedula)
            
            if last_record and last_record.get('verification_type') == 'entrada':
                return 'salida'
            else:
                return 'entrada'
                
        except Exception as e:
            self.logger.error(f"Error detecting entry/exit type: {str(e)}")
            return 'entrada'  # Default to entry
    
    def _validate_cedula(self, cedula: str) -> bool:
        """
        Validate document ID format.
        
        Args:
            cedula: Document ID to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not cedula or len(cedula) < 6:
            return False
        
        # Check if it contains only digits
        if not cedula.isdigit():
            return False
        
        return True
    
    async def _save_local_record(self, response: VerificationResponse, request: VerificationRequest) -> None:
        """
        Save verification record to local database.
        
        Args:
            response: VerificationResponse with verification results
            request: Original VerificationRequest
        """
        try:
            record_data = {
                'id': response.record_id or str(uuid.uuid4()),
                'user_id': response.user_data.get('id') if response.user_data else None,
                'cedula': response.user_data.get('cedula') if response.user_data else request.cedula,
                'timestamp': response.timestamp,
                'method': 'online' if response.method_used == 'facial' else 'offline',
                'verification_type': response.method_used,
                'confidence_score': response.confidence,
                'is_synced': response.method_used == 'facial',  # Facial records are already synced via API
                'location_name': response.user_data.get('ubicacion', 'Terminal') if response.user_data else 'Terminal',
                'device_id': self.config.api.terminal_id,
                'created_at': response.timestamp
            }
            
            await self.db_manager.save_access_record(record_data)
            self.logger.info(f"Local record saved: {record_data['id']}")
            
        except Exception as e:
            self.logger.error(f"Failed to save local record: {str(e)}")
    
    # ==========================================
    # IMAGE PROCESSING UTILITIES
    # ==========================================
    
    def prepare_image_for_verification(self, image: Union[np.ndarray, bytes]) -> bytes:
        """
        Prepare image for verification by converting to appropriate format.
        
        Args:
            image: Image as numpy array or bytes
        
        Returns:
            Image as bytes in JPEG format
        """
        try:
            if isinstance(image, np.ndarray):
                # Convert numpy array to bytes
                success, buffer = cv2.imencode('.jpg', image)
                if success:
                    return buffer.tobytes()
                else:
                    raise ValueError("Failed to encode image")
            
            elif isinstance(image, bytes):
                # Already in bytes format
                return image
            
            else:
                raise ValueError(f"Unsupported image type: {type(image)}")
                
        except Exception as e:
            self.logger.error(f"Error preparing image: {str(e)}")
            raise
    
    def validate_image_quality(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        Validate image quality for verification.
        
        Args:
            image_bytes: Image as bytes
        
        Returns:
            Dictionary with validation results
        """
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                return {'valid': False, 'error': 'Cannot decode image'}
            
            height, width = image.shape[:2]
            
            # Basic quality checks
            checks = {
                'valid': True,
                'width': width,
                'height': height,
                'size_ok': width >= 240 and height >= 240,
                'aspect_ratio': width / height,
                'brightness': np.mean(image),
                'contrast': np.std(image)
            }
            
            # Determine overall validity
            checks['valid'] = (
                checks['size_ok'] and
                0.5 <= checks['aspect_ratio'] <= 2.0 and
                30 <= checks['brightness'] <= 220 and
                checks['contrast'] > 20
            )
            
            return checks
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    # ==========================================
    # STATUS AND MONITORING
    # ==========================================
    
    def get_verification_status(self) -> Dict[str, Any]:
        """
        Get current verification service status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'service_active': True,
            'current_verification': self.current_verification,
            'verification_attempts': self.verification_attempts.copy(),
            'configuration': {
                'max_facial_attempts': self.max_facial_attempts,
                'max_fingerprint_attempts': self.max_fingerprint_attempts,
                'verification_timeout': self.verification_timeout,
                'fallback_enabled': True
            },
            'hardware_status': {
                'camera_enabled': self.config.hardware.camera_enabled,
                'fingerprint_enabled': self.config.hardware.fingerprint_enabled,
                'api_connectivity': self.api_client.is_online
            },
            'timestamp': datetime.utcnow().isoformat()
        }


# Global verification service instance
_verification_service = None


def get_verification_service() -> VerificationService:
    """Get the global verification service instance"""
    global _verification_service
    if _verification_service is None:
        _verification_service = VerificationService()
    return _verification_service


if __name__ == "__main__":
    # Test the verification service
    import asyncio
    
    async def test_verification_service():
        verification_service = get_verification_service()
        
        # Test status
        print("Testing verification status...")
        status = verification_service.get_verification_status()
        print(f"Status: {status}")
        
        # Test image quality validation
        print("Testing image quality validation...")
        # Create a test image
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        test_image_bytes = verification_service.prepare_image_for_verification(test_image)
        quality = verification_service.validate_image_quality(test_image_bytes)
        print(f"Image quality: {quality}")
        
        # Test manual verification
        print("Testing manual verification...")
        manual_request = VerificationRequest(
            method='manual',
            cedula='12345678'
        )
        
        manual_response = await verification_service.verify_user(manual_request)
        print(f"Manual verification: {manual_response}")
    
    asyncio.run(test_verification_service())