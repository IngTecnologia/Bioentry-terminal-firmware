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
    """Logger especializado para el terminal biométrico"""
    
    def __init__(self, name: str = "terminal"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.config = get_config()
        
        # Evitar duplicar handlers
        if not self.logger.handlers:
            self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Configura el logger con handlers de archivo y consola"""
        # Configurar nivel de logging
        level = getattr(logging, self.config.logging.level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Crear directorio de logs si no existe
        log_path = self.config.get_full_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Formatter
        formatter = logging.Formatter(
            self.config.logging.format,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Handler para archivo con rotación
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=self.config.logging.max_file_size,
            backupCount=self.config.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        
        # Handler para consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        
        # Añadir handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, **kwargs) -> None:
        """Log nivel DEBUG"""
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log nivel INFO"""
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log nivel WARNING"""
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log nivel ERROR"""
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log nivel CRITICAL"""
        self._log_with_context(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs) -> None:
        """Log de excepción con traceback"""
        self._log_with_context(logging.ERROR, message, exc_info=True, **kwargs)
    
    def _log_with_context(self, level: int, message: str, **kwargs) -> None:
        """Log con contexto adicional"""
        # Extraer contexto especial
        context = {
            'terminal_id': self.config.api.terminal_id,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        # Añadir contexto adicional si se proporciona
        if kwargs:
            context.update(kwargs)
        
        # Formatear mensaje con contexto
        if context:
            context_str = " | ".join([f"{k}={v}" for k, v in context.items() if k != 'exc_info'])
            formatted_message = f"{message} | {context_str}"
        else:
            formatted_message = message
        
        # Log
        self.logger.log(level, formatted_message, exc_info=kwargs.get('exc_info', False))
    
    def log_hardware_event(self, component: str, event: str, status: str, **kwargs) -> None:
        """Log específico para eventos de hardware"""
        self.info(
            f"Hardware Event: {component}",
            component=component,
            event=event,
            status=status,
            **kwargs
        )
    
    def log_api_request(self, endpoint: str, method: str, status_code: int, response_time: float, **kwargs) -> None:
        """Log específico para requests de API"""
        self.info(
            f"API Request: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=round(response_time * 1000, 2),
            **kwargs
        )
    
    def log_user_interaction(self, user_id: Optional[str], action: str, result: str, **kwargs) -> None:
        """Log específico para interacciones de usuario"""
        self.info(
            f"User Interaction: {action}",
            user_id=user_id or "unknown",
            action=action,
            result=result,
            **kwargs
        )
    
    def log_state_transition(self, from_state: str, to_state: str, trigger: str, **kwargs) -> None:
        """Log específico para transiciones de estado"""
        self.info(
            f"State Transition: {from_state} -> {to_state}",
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            **kwargs
        )
    
    def log_sync_event(self, event_type: str, records_count: int, success: bool, **kwargs) -> None:
        """Log específico para eventos de sincronización"""
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
        """Log específico para métricas de rendimiento"""
        self.debug(
            f"Performance: {metric_name}",
            metric_name=metric_name,
            value=value,
            unit=unit,
            **kwargs
        )
    
    def log_security_event(self, event_type: str, severity: str, details: str, **kwargs) -> None:
        """Log específico para eventos de seguridad"""
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
    """Logger especializado para métricas de rendimiento"""
    
    def __init__(self, logger: TerminalLogger):
        self.logger = logger
        self.start_times: Dict[str, float] = {}
    
    def start_timing(self, operation: str) -> None:
        """Inicia el timing de una operación"""
        import time
        self.start_times[operation] = time.time()
    
    def end_timing(self, operation: str, **kwargs) -> float:
        """Finaliza el timing y registra la métrica"""
        import time
        if operation not in self.start_times:
            self.logger.warning(f"No se encontró tiempo de inicio para operación: {operation}")
            return 0.0
        
        elapsed_time = time.time() - self.start_times[operation]
        elapsed_ms = elapsed_time * 1000
        
        self.logger.log_performance_metric(
            operation,
            elapsed_ms,
            unit="ms",
            **kwargs
        )
        
        # Limpiar
        del self.start_times[operation]
        
        return elapsed_ms
    
    def time_operation(self, operation: str):
        """Decorator para timing automático de operaciones"""
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
    """Logger especializado para manejo de errores"""
    
    def __init__(self, logger: TerminalLogger):
        self.logger = logger
    
    def log_hardware_error(self, component: str, error: Exception, **kwargs) -> None:
        """Log específico para errores de hardware"""
        self.logger.error(
            f"Hardware Error: {component}",
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs
        )
    
    def log_api_error(self, endpoint: str, error: Exception, status_code: Optional[int] = None, **kwargs) -> None:
        """Log específico para errores de API"""
        self.logger.error(
            f"API Error: {endpoint}",
            endpoint=endpoint,
            error_type=type(error).__name__,
            error_message=str(error),
            status_code=status_code,
            **kwargs
        )
    
    def log_database_error(self, operation: str, error: Exception, **kwargs) -> None:
        """Log específico para errores de base de datos"""
        self.logger.error(
            f"Database Error: {operation}",
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            **kwargs
        )
    
    def log_critical_system_error(self, component: str, error: Exception, **kwargs) -> None:
        """Log para errores críticos del sistema"""
        self.logger.critical(
            f"Critical System Error: {component}",
            component=component,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            **kwargs
        )


# Instancias globales
_main_logger = None
_performance_logger = None
_error_logger = None


def get_logger(name: str = "terminal") -> TerminalLogger:
    """Obtiene el logger principal"""
    global _main_logger
    if _main_logger is None:
        _main_logger = TerminalLogger(name)
    return _main_logger


def get_performance_logger() -> PerformanceLogger:
    """Obtiene el logger de rendimiento"""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger(get_logger())
    return _performance_logger


def get_error_logger() -> ErrorLogger:
    """Obtiene el logger de errores"""
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger(get_logger())
    return _error_logger


def setup_logging():
    """Inicializa el sistema de logging"""
    # Crear directorios necesarios
    config = get_config()
    log_path = config.get_full_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Inicializar loggers
    get_logger()
    get_performance_logger()
    get_error_logger()
    
    # Log inicial
    logger = get_logger()
    logger.info("Sistema de logging inicializado", version="1.0.0")


if __name__ == "__main__":
    # Test del sistema de logging
    setup_logging()
    
    logger = get_logger()
    performance = get_performance_logger()
    error_logger = get_error_logger()
    
    # Test logs básicos
    logger.info("Test de logging básico")
    logger.debug("Test de debug")
    logger.warning("Test de warning")
    logger.error("Test de error")
    
    # Test logs especializados
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
    
    print("Tests de logging completados. Revisa el archivo de log.")