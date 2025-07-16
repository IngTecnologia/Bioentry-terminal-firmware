from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
from collections import defaultdict

from utils.config import get_config
from utils.logger import get_logger


class SystemState(Enum):
    """Estados del sistema del terminal"""
    IDLE = "idle"
    ACTIVATION = "activation"
    FACIAL_RECOGNITION = "facial_recognition"
    FINGERPRINT_VERIFICATION = "fingerprint_verification"
    MANUAL_ENTRY = "manual_entry"
    CONFIRMATION = "confirmation"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    SHUTDOWN = "shutdown"


@dataclass
class StateData:
    """Datos asociados a un estado específico"""
    user_data: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    """Definición de una transición de estado"""
    from_state: SystemState
    to_state: SystemState
    trigger: str
    condition: Optional[Callable] = None
    action: Optional[Callable] = None


class StateManagerError(Exception):
    """Excepción para errores del gestor de estados"""
    pass


class InvalidStateTransitionError(StateManagerError):
    """Excepción para transiciones inválidas"""
    pass


class StateManager:
    """
    Gestor de estados centralizado para el terminal biométrico.
    Implementa una máquina de estados finita con transiciones controladas.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Estado actual
        self.current_state = SystemState.IDLE
        self.previous_state: Optional[SystemState] = None
        self.state_data = StateData()
        
        # Historial de estados
        self.state_history: List[Dict[str, Any]] = []
        
        # Contadores de intentos por contexto
        self.attempt_counters: Dict[str, int] = defaultdict(int)
        
        # Timestamps
        self.state_start_time = datetime.now()
        self.last_activity_time = datetime.now()
        
        # Configurar transiciones válidas
        self.valid_transitions = self._define_valid_transitions()
        
        # Callbacks para eventos de estado
        self.state_enter_callbacks: Dict[SystemState, List[Callable]] = defaultdict(list)
        self.state_exit_callbacks: Dict[SystemState, List[Callable]] = defaultdict(list)
        self.transition_callbacks: List[Callable] = []
        
        # Configurar timeouts
        self.state_timeouts: Dict[SystemState, int] = {
            SystemState.ACTIVATION: self.config.operation.timeout_seconds,
            SystemState.FACIAL_RECOGNITION: self.config.operation.timeout_seconds,
            SystemState.FINGERPRINT_VERIFICATION: self.config.operation.timeout_seconds,
            SystemState.MANUAL_ENTRY: self.config.operation.timeout_seconds * 2,
            SystemState.CONFIRMATION: 5,  # 5 segundos para confirmación
        }
        
        # Task de timeout actual
        self._timeout_task: Optional[asyncio.Task] = None
        
        self.logger.info("State Manager inicializado", initial_state=self.current_state.value)
    
    def _define_valid_transitions(self) -> Dict[SystemState, List[SystemState]]:
        """Define las transiciones válidas entre estados"""
        return {
            SystemState.IDLE: [
                SystemState.ACTIVATION,
                SystemState.MAINTENANCE,
                SystemState.SHUTDOWN
            ],
            SystemState.ACTIVATION: [
                SystemState.FACIAL_RECOGNITION,
                SystemState.FINGERPRINT_VERIFICATION,
                SystemState.MANUAL_ENTRY,
                SystemState.IDLE,
                SystemState.ERROR
            ],
            SystemState.FACIAL_RECOGNITION: [
                SystemState.CONFIRMATION,
                SystemState.FINGERPRINT_VERIFICATION,
                SystemState.MANUAL_ENTRY,
                SystemState.IDLE,
                SystemState.ERROR
            ],
            SystemState.FINGERPRINT_VERIFICATION: [
                SystemState.CONFIRMATION,
                SystemState.MANUAL_ENTRY,
                SystemState.IDLE,
                SystemState.ERROR
            ],
            SystemState.MANUAL_ENTRY: [
                SystemState.CONFIRMATION,
                SystemState.IDLE,
                SystemState.ERROR
            ],
            SystemState.CONFIRMATION: [
                SystemState.IDLE
            ],
            SystemState.ERROR: [
                SystemState.IDLE,
                SystemState.MAINTENANCE,
                SystemState.SHUTDOWN
            ],
            SystemState.MAINTENANCE: [
                SystemState.IDLE,
                SystemState.SHUTDOWN
            ],
            SystemState.SHUTDOWN: []  # Estado terminal
        }
    
    async def transition_to(self, new_state: SystemState, trigger: str = "manual", 
                          data: Optional[StateData] = None) -> bool:
        """
        Ejecuta una transición controlada entre estados.
        
        Args:
            new_state: Estado de destino
            trigger: Evento que desencadena la transición
            data: Datos asociados al nuevo estado
            
        Returns:
            bool: True si la transición fue exitosa
        """
        try:
            # Validar transición
            if new_state not in self.valid_transitions[self.current_state]:
                raise InvalidStateTransitionError(
                    f"Transición inválida: {self.current_state.value} -> {new_state.value}"
                )
            
            # Cancelar timeout anterior
            if self._timeout_task:
                self._timeout_task.cancel()
                self._timeout_task = None
            
            # Ejecutar callbacks de salida del estado actual
            await self._execute_exit_callbacks(self.current_state)
            
            # Registrar transición en historial
            transition_record = {
                "from_state": self.current_state.value,
                "to_state": new_state.value,
                "trigger": trigger,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.state_start_time).total_seconds(),
                "data": data.metadata if data else {}
            }
            self.state_history.append(transition_record)
            
            # Logging de transición
            self.logger.log_state_transition(
                self.current_state.value,
                new_state.value,
                trigger,
                duration_seconds=transition_record["duration_seconds"]
            )
            
            # Actualizar estado
            self.previous_state = self.current_state
            self.current_state = new_state
            self.state_data = data or StateData()
            self.state_start_time = datetime.now()
            self.last_activity_time = datetime.now()
            
            # Reset contadores si es necesario
            if self._should_reset_attempts(new_state):
                self.attempt_counters.clear()
            
            # Ejecutar callbacks de entrada al nuevo estado
            await self._execute_enter_callbacks(new_state)
            
            # Ejecutar callbacks de transición
            await self._execute_transition_callbacks(transition_record)
            
            # Configurar timeout para el nuevo estado
            await self._setup_state_timeout(new_state)
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error en transición de estado: {e}",
                from_state=self.current_state.value,
                to_state=new_state.value,
                trigger=trigger
            )
            
            # En caso de error, transicionar a estado de error
            if new_state != SystemState.ERROR:
                await self._emergency_transition_to_error(str(e))
            
            return False
    
    async def _execute_exit_callbacks(self, state: SystemState) -> None:
        """Ejecuta callbacks de salida de un estado"""
        for callback in self.state_exit_callbacks[state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state, self.state_data)
                else:
                    callback(state, self.state_data)
            except Exception as e:
                self.logger.error(f"Error en callback de salida: {e}", state=state.value)
    
    async def _execute_enter_callbacks(self, state: SystemState) -> None:
        """Ejecuta callbacks de entrada a un estado"""
        for callback in self.state_enter_callbacks[state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state, self.state_data)
                else:
                    callback(state, self.state_data)
            except Exception as e:
                self.logger.error(f"Error en callback de entrada: {e}", state=state.value)
    
    async def _execute_transition_callbacks(self, transition_record: Dict[str, Any]) -> None:
        """Ejecuta callbacks de transición"""
        for callback in self.transition_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(transition_record)
                else:
                    callback(transition_record)
            except Exception as e:
                self.logger.error(f"Error en callback de transición: {e}")
    
    async def _setup_state_timeout(self, state: SystemState) -> None:
        """Configura el timeout para un estado"""
        if state in self.state_timeouts:
            timeout_seconds = self.state_timeouts[state]
            self._timeout_task = asyncio.create_task(
                self._handle_state_timeout(state, timeout_seconds)
            )
    
    async def _handle_state_timeout(self, state: SystemState, timeout_seconds: int) -> None:
        """Maneja el timeout de un estado"""
        try:
            await asyncio.sleep(timeout_seconds)
            
            # Verificar que seguimos en el mismo estado
            if self.current_state == state:
                self.logger.warning(
                    f"Timeout en estado {state.value}",
                    timeout_seconds=timeout_seconds
                )
                
                # Transición automática a IDLE por timeout
                await self.transition_to(SystemState.IDLE, trigger="timeout")
                
        except asyncio.CancelledError:
            # Timeout cancelado por transición normal
            pass
        except Exception as e:
            self.logger.error(f"Error en timeout de estado: {e}", state=state.value)
    
    def _should_reset_attempts(self, new_state: SystemState) -> bool:
        """Determina si se deben resetear los contadores de intentos"""
        # Reset intentos cuando volvemos a IDLE o cambiamos de contexto de verificación
        if new_state == SystemState.IDLE:
            return True
        
        # Reset cuando cambiamos entre diferentes métodos de verificación
        verification_states = {
            SystemState.FACIAL_RECOGNITION,
            SystemState.FINGERPRINT_VERIFICATION,
            SystemState.MANUAL_ENTRY
        }
        
        if (self.current_state in verification_states and 
            new_state in verification_states and 
            self.current_state != new_state):
            return True
        
        return False
    
    async def _emergency_transition_to_error(self, error_message: str) -> None:
        """Transición de emergencia al estado de error"""
        try:
            error_data = StateData(
                error_info={
                    "message": error_message,
                    "timestamp": datetime.now().isoformat(),
                    "previous_state": self.current_state.value
                }
            )
            
            self.previous_state = self.current_state
            self.current_state = SystemState.ERROR
            self.state_data = error_data
            self.state_start_time = datetime.now()
            
            self.logger.error(
                "Transición de emergencia al estado de error",
                error_message=error_message,
                previous_state=self.previous_state.value if self.previous_state else None
            )
            
        except Exception as e:
            self.logger.critical(f"Error crítico en transición de emergencia: {e}")
    
    # ==================== GESTIÓN DE INTENTOS ====================
    
    def increment_attempts(self, context: str = "default") -> int:
        """Incrementa el contador de intentos para un contexto específico"""
        key = f"{self.current_state.value}_{context}"
        self.attempt_counters[key] += 1
        attempts = self.attempt_counters[key]
        
        self.logger.debug(
            f"Intentos incrementados en {context}",
            state=self.current_state.value,
            context=context,
            attempts=attempts
        )
        
        return attempts
    
    def get_attempts(self, context: str = "default") -> int:
        """Obtiene el número actual de intentos para un contexto"""
        key = f"{self.current_state.value}_{context}"
        return self.attempt_counters[key]
    
    def reset_attempts(self, context: Optional[str] = None) -> None:
        """Resetea contadores de intentos"""
        if context:
            key = f"{self.current_state.value}_{context}"
            self.attempt_counters[key] = 0
        else:
            self.attempt_counters.clear()
    
    # ==================== GESTIÓN DE CALLBACKS ====================
    
    def on_state_enter(self, state: SystemState, callback: Callable) -> None:
        """Registra un callback para cuando se entra a un estado"""
        self.state_enter_callbacks[state].append(callback)
    
    def on_state_exit(self, state: SystemState, callback: Callable) -> None:
        """Registra un callback para cuando se sale de un estado"""
        self.state_exit_callbacks[state].append(callback)
    
    def on_transition(self, callback: Callable) -> None:
        """Registra un callback para cualquier transición"""
        self.transition_callbacks.append(callback)
    
    # ==================== INFORMACIÓN Y ESTADO ====================
    
    def get_current_state(self) -> SystemState:
        """Obtiene el estado actual"""
        return self.current_state
    
    def get_state_data(self) -> StateData:
        """Obtiene los datos del estado actual"""
        return self.state_data
    
    def get_state_duration(self) -> float:
        """Obtiene la duración del estado actual en segundos"""
        return (datetime.now() - self.state_start_time).total_seconds()
    
    def get_last_activity_time(self) -> datetime:
        """Obtiene el timestamp de la última actividad"""
        return self.last_activity_time
    
    def update_activity(self) -> None:
        """Actualiza el timestamp de última actividad"""
        self.last_activity_time = datetime.now()
    
    def is_in_verification_state(self) -> bool:
        """Determina si estamos en un estado de verificación"""
        verification_states = {
            SystemState.FACIAL_RECOGNITION,
            SystemState.FINGERPRINT_VERIFICATION,
            SystemState.MANUAL_ENTRY
        }
        return self.current_state in verification_states
    
    def is_idle(self) -> bool:
        """Determina si estamos en estado IDLE"""
        return self.current_state == SystemState.IDLE
    
    def can_transition_to(self, state: SystemState) -> bool:
        """Verifica si una transición es válida"""
        return state in self.valid_transitions[self.current_state]
    
    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtiene el historial de estados"""
        if limit:
            return self.state_history[-limit:]
        return self.state_history.copy()
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas del gestor de estados"""
        # Contar tiempo por estado
        state_durations = defaultdict(float)
        for record in self.state_history:
            state_durations[record["from_state"]] += record["duration_seconds"]
        
        # Contar transiciones
        transition_counts = defaultdict(int)
        for record in self.state_history:
            transition_key = f"{record['from_state']} -> {record['to_state']}"
            transition_counts[transition_key] += 1
        
        return {
            "current_state": self.current_state.value,
            "state_duration_seconds": self.get_state_duration(),
            "total_transitions": len(self.state_history),
            "state_durations": dict(state_durations),
            "transition_counts": dict(transition_counts),
            "attempt_counters": dict(self.attempt_counters)
        }
    
    # ==================== UTILIDADES PARA TESTING ====================
    
    def force_state(self, state: SystemState, data: Optional[StateData] = None) -> None:
        """
        Fuerza un estado sin validaciones (solo para testing).
        ¡NO USAR EN PRODUCCIÓN!
        """
        if not self.config.is_mock_mode():
            raise StateManagerError("force_state solo disponible en modo mock")
        
        self.logger.warning(
            "Forzando estado (modo testing)",
            from_state=self.current_state.value,
            to_state=state.value
        )
        
        self.previous_state = self.current_state
        self.current_state = state
        self.state_data = data or StateData()
        self.state_start_time = datetime.now()
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Obtiene información de debug del gestor de estados"""
        return {
            "current_state": self.current_state.value,
            "previous_state": self.previous_state.value if self.previous_state else None,
            "state_duration": self.get_state_duration(),
            "state_data": {
                "user_data": self.state_data.user_data,
                "verification_result": self.state_data.verification_result,
                "error_info": self.state_data.error_info,
                "metadata": self.state_data.metadata
            },
            "attempt_counters": dict(self.attempt_counters),
            "valid_transitions": [s.value for s in self.valid_transitions[self.current_state]],
            "timeout_active": self._timeout_task is not None and not self._timeout_task.done()
        }


# Instancia global del gestor de estados
_state_manager = None


def get_state_manager() -> StateManager:
    """Obtiene la instancia global del gestor de estados"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


# Funciones de conveniencia para uso común
async def transition_to_idle(trigger: str = "manual") -> bool:
    """Transición rápida al estado IDLE"""
    return await get_state_manager().transition_to(SystemState.IDLE, trigger)


async def transition_to_error(error_message: str) -> bool:
    """Transición rápida al estado ERROR"""
    error_data = StateData(
        error_info={
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }
    )
    return await get_state_manager().transition_to(SystemState.ERROR, "error", error_data)


def get_current_state() -> SystemState:
    """Obtiene el estado actual"""
    return get_state_manager().get_current_state()


def is_in_verification_state() -> bool:
    """Determina si estamos en un estado de verificación"""
    return get_state_manager().is_in_verification_state()


if __name__ == "__main__":
    # Test básico del state manager
    async def test_state_manager():
        sm = get_state_manager()
        
        print(f"Estado inicial: {sm.get_current_state().value}")
        
        # Test transición válida
        success = await sm.transition_to(SystemState.ACTIVATION, "test_trigger")
        print(f"Transición a ACTIVATION: {'exitosa' if success else 'fallida'}")
        print(f"Estado actual: {sm.get_current_state().value}")
        
        # Test transición inválida
        try:
            await sm.transition_to(SystemState.CONFIRMATION, "invalid_trigger")
        except InvalidStateTransitionError as e:
            print(f"Transición inválida detectada: {e}")
        
        # Test incremento de intentos
        attempts = sm.increment_attempts("facial")
        print(f"Intentos de reconocimiento facial: {attempts}")
        
        # Test estadísticas
        stats = sm.get_state_statistics()
        print(f"Estadísticas: {stats}")
        
        # Test callback
        def on_enter_idle(state, data):
            print(f"Callback: Entrando al estado {state.value}")
        
        sm.on_state_enter(SystemState.IDLE, on_enter_idle)
        
        # Volver a IDLE
        await sm.transition_to(SystemState.IDLE, "test_complete")
        
        # Test timeout
        await sm.transition_to(SystemState.FACIAL_RECOGNITION, "timeout_test")
        print("Esperando timeout...")
        await asyncio.sleep(2)
        print(f"Estado después de timeout: {sm.get_current_state().value}")
        
        # Debug info
        debug = sm.get_debug_info()
        print(f"Debug info: {debug}")
    
    asyncio.run(test_state_manager())