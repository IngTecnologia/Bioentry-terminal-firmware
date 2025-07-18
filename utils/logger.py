import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional, Dict, Any
import json
import traceback
from .config import get_config


class TerminalLogger:
    """Specialized logger for the biometric terminal"""
    
    def __init__(self, name: str = "terminal"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        # Avoid duplicating handlers
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Configure logger with file and console handlers"""
        # Configure logging level
        level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Create logs directory if it doesn't exist
        log_path = self.config.get_full_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Formatter
        formatter = logging.Formatter(
            self.config.logging.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=self.config.logging.max_file_size,
            backupCount=self.config.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log DEBUG level"""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log INFO level"""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log WARNING level"""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log ERROR level"""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log CRITICAL level"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback"""
        self._log_with_context(logging.ERROR, message, exc_info=True, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs) -> None:
        """Log with additional context"""
        # Extract special context
        context = {
            'terminal_id': self.config.api.terminal_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        # Add additional context if provided
        if kwargs:
            context.update(kwargs)
        
        # Format message with context
        if context:
            context_str = " | ".join([f"{k}={v}" for k, v in context.items() if k != 'exc_info'])
            formatted_message = f"{message} | {context_str}"
        else:
            formatted_message = message
        
        # Log
        self.logger.log(level, formatted_message, exc_info=kwargs.get('exc_info', False))
    
    def log_hardware_event(self, component: str, event: str, status: str, **kwargs) -> None:
        """Log specific to hardware events"""
        self.info(
            f"Hardware Event: {component}",
            component=component,
            event=event,
            status=status,
            **kwargs
        )
    
    def log_api_request(self, endpoint: str, method: str, status_code: int, response_time: float, **kwargs) -> None:
        """Log specific to API requests"""
        self.info(
            f"API Request: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=round(response_time * 1000, 2),
            **kwargs
        )
    
    def log_user_interaction(self, user_id: Optional[str], action: str, result: str, **kwargs) -> None:
        """Log specific to user interactions"""
        self.info(
            f"User Interaction: {action}",
            user_id=user_id or "unknown",
            action=action,
            result=result,
            **kwargs
        )
    
    def log_state_transition(self, from_state: str, to_state: str, trigger: str, **kwargs) -> None:
        """Log specific to state transitions"""
        self.info(
            f"State Transition: {from_state} -> {to_state}",
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            **kwargs
        )
    
    def log_sync_event(self, event_type: str, records_count: int, success: bool, **kwargs) -> None:
        """Log specific to sync events"""
        level = logging.INFO if success else logging.WARNING
        self._log_with_context(
            level,
            f"Sync Event: {event_type}",
            event_type=event_type,
            records_count=records_count,
            success=success,
            **kwargs
        )
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = "ms", **kwargs) -> None:
        """Log specific to performance metrics"""
        self.debug(
            f"Performance: {metric_name}",
            metric_name=metric_name,
            value=value,
            unit=unit,
            **kwargs
        )
    
    def log_security_event(self, event_type: str, severity: str, details: str, **kwargs) -> None:
        """Log specific to security events"""
        level = logging.WARNING if severity == "medium" else logging.ERROR
        self._log_with_context(
            level,
            f"Security Event: {event_type}",
            event_type=event_type,
            severity=severity,
            details=details,
            **kwargs
        )


class PerformanceLogger:
    """Specialized logger for performance metrics"""
    
    def __init__(self, logger: TerminalLogger):
        self.logger = logger
        self.start_times: Dict[str, float] = {}
    
    def start_timing(self, operation: str) -> None:
        """Start timing of an operation"""
        import time
        self.start_times[operation] = time.time()
    
    def end_timing(self, operation: str, **kwargs) -> float:
        """End timing and log the metric"""
        import time
        if operation not in self.start_times:
            self.logger.warning(f"No start time found for operation: {operation}")
            return 0.0
        
        elapsed_time = time.time() - self.start_times[operation]
        elapsed_ms = elapsed_time * 1000
        
        self.logger.log_performance_metric(
            operation,
            elapsed_ms,
            unit="ms",
            **kwargs
        )
        
        # Clean up
        del self.start_times[operation]
        
        return elapsed_ms
    
    def time_operation(self, operation: str):
        """Decorator for automatic operation timing"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                self.start_timing(operation)
                try:
                    result = func(*args, **kwargs)
                    self.end_timing(operation, status="success")
                    return result
                except Exception as e:
                    self.end_timing(operation, status="error", error=str(e))
                    raise
            return wrapper
        return decorator


class ErrorLogger:
    """Specialized logger for error handling"""
    
    def __init__(self, logger: TerminalLogger):
        self.logger = logger
    
    def log_hardware_error(self, component: str, error: Exception, **kwargs) -> None:
        """Log specific to hardware errors"""
        self.logger.error(
            f"Hardware Error: {component}",
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs
        )
    
    def log_api_error(self, endpoint: str, error: Exception, status_code: Optional[int] = None, **kwargs) -> None:
        """Log specific to API errors"""
        self.logger.error(
            f"API Error: {endpoint}",
            endpoint=endpoint,
            error_type=type(error).__name__,
            error_message=str(error),
            status_code=status_code,
            **kwargs
        )
    
    def log_database_error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log specific to database errors"""
        self.logger.error(
            f"Database Error: {operation}",
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs
        )
    
    def log_critical_system_error(self, component: str, error: Exception, **kwargs) -> None:
        """Log for critical system errors"""
        self.logger.critical(
            f"Critical System Error: {component}",
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            **kwargs
        )


# Global instances
_main_logger = None
_performance_logger = None
_error_logger = None


def get_logger(name: str = "terminal") -> TerminalLogger:
    """Get the main logger"""
    global _main_logger
    if _main_logger is None:
        _main_logger = TerminalLogger(name)
    return _main_logger


def get_performance_logger() -> PerformanceLogger:
    """Get the performance logger"""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger(get_logger())
    return _performance_logger


def get_error_logger() -> ErrorLogger:
    """Get the error logger"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger(get_logger())
    return _error_logger


def setup_logging():
    """Initialize the logging system"""
    # Create necessary directories
    config = get_config()
    log_path = config.get_full_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize loggers
    get_logger()
    get_performance_logger()
    get_error_logger()
    
    # Initial log
    logger = get_logger()
    logger.info("Logging system initialized", version="1.0.0")


if __name__ == "__main__":
    # Test logging system
    setup_logging()
    
    logger = get_logger()
    performance = get_performance_logger()
    error_logger = get_error_logger()
    
    # Test basic logs
    logger.info("Basic logging test")
    logger.debug("Debug test")
    logger.warning("Warning test")
    logger.error("Error test")
    
    # Test specialized logs
    logger.log_hardware_event("camera", "initialization", "success")
    logger.log_api_request("/verify", "POST", 200, 0.5)
    logger.log_user_interaction("12345", "facial_verification", "success")
    logger.log_state_transition("idle", "recognition", "proximity_detected")
    
    # Test performance logging
    performance.start_timing("test_operation")
    import time
    time.sleep(0.1)
    performance.end_timing("test_operation")
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_logger.log_hardware_error("test_component", e)
    
    print("Logging tests completed. Check the log file.")