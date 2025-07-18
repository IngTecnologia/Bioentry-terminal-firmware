from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import asyncio
from collections import defaultdict

from utils.config import get_config
from utils.logger import get_logger


class SystemState(Enum):
    """Terminal system states"""
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
    """Data associated with a specific state"""
    user_data: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    """Definition of a state transition"""
    from_state: SystemState
    to_state: SystemState
    trigger: str
    condition: Optional[Callable] = None
    action: Optional[Callable] = None


class StateManagerError(Exception):
    """Exception for state manager errors"""
    pass


class InvalidStateTransitionError(StateManagerError):
    """Exception for invalid transitions"""
    pass


class StateManager:
    """
    Centralized state manager for the biometric terminal.
    Implements a finite state machine with controlled transitions.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Current state
        self.current_state = SystemState.IDLE
        self.previous_state: Optional[SystemState] = None
        self.state_data = StateData()
        
        # State history
        self.state_history: List[Dict[str, Any]] = []
        
        # Attempt counters by context
        self.attempt_counters: Dict[str, int] = defaultdict(int)
        
        # Timestamps
        self.state_start_time = datetime.now()
        self.last_activity_time = datetime.now()
        
        # Configure valid transitions
        self.valid_transitions = self._define_valid_transitions()
        
        # Callbacks for state events
        self.state_enter_callbacks: Dict[SystemState, List[Callable]] = defaultdict(list)
        self.state_exit_callbacks: Dict[SystemState, List[Callable]] = defaultdict(list)
        self.transition_callbacks: List[Callable] = []
        
        # Configure timeouts
        self.state_timeouts: Dict[SystemState, int] = {
            SystemState.ACTIVATION: self.config.operation.timeout_seconds,
            SystemState.FACIAL_RECOGNITION: self.config.operation.timeout_seconds,
            SystemState.FINGERPRINT_VERIFICATION: self.config.operation.timeout_seconds,
            SystemState.MANUAL_ENTRY: self.config.operation.timeout_seconds * 2,
            SystemState.CONFIRMATION: 5,  # 5 seconds for confirmation
        }
        
        # Current timeout task
        self._timeout_task: Optional[asyncio.Task] = None
        
        self.logger.info("State Manager initialized", initial_state=self.current_state.value)
    
    def _define_valid_transitions(self) -> Dict[SystemState, List[SystemState]]:
        """Define valid transitions between states"""
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
            SystemState.SHUTDOWN: []  # Terminal state
        }
    
    async def transition_to(self, new_state: SystemState, trigger: str = "manual", 
                          data: Optional[StateData] = None) -> bool:
        """
        Execute a controlled transition between states.
        
        Args:
            new_state: Target state
            trigger: Event that triggers the transition
            data: Data associated with the new state
            
        Returns:
            bool: True if transition was successful
        """
        try:
            # Validate transition
            if new_state not in self.valid_transitions[self.current_state]:
                raise InvalidStateTransitionError(
                    f"Invalid transition: {self.current_state.value} -> {new_state.value}"
                )
            
            # Cancel previous timeout
            if self._timeout_task:
                self._timeout_task.cancel()
                self._timeout_task = None
            
            # Execute exit callbacks for current state
            await self._execute_exit_callbacks(self.current_state)
            
            # Register transition in history
            transition_record = {
                "from_state": self.current_state.value,
                "to_state": new_state.value,
                "trigger": trigger,
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.state_start_time).total_seconds(),
                "data": data.metadata if data else {}
            }
            self.state_history.append(transition_record)
            
            # Log transition
            self.logger.log_state_transition(
                self.current_state.value,
                new_state.value,
                trigger,
                duration_seconds=transition_record["duration_seconds"]
            )
            
            # Update state
            self.previous_state = self.current_state
            self.current_state = new_state
            self.state_data = data or StateData()
            self.state_start_time = datetime.now()
            self.last_activity_time = datetime.now()
            
            # Reset counters if necessary
            if self._should_reset_attempts(new_state):
                self.attempt_counters.clear()
            
            # Execute enter callbacks for new state
            await self._execute_enter_callbacks(new_state)
            
            # Execute transition callbacks
            await self._execute_transition_callbacks(transition_record)
            
            # Configure timeout for new state
            await self._setup_state_timeout(new_state)
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error in state transition: {e}",
                from_state=self.current_state.value,
                to_state=new_state.value,
                trigger=trigger
            )
            
            # In case of error, transition to error state
            if new_state != SystemState.ERROR:
                await self._emergency_transition_to_error(str(e))
            
            return False
    
    async def _execute_exit_callbacks(self, state: SystemState) -> None:
        """Execute exit callbacks for a state"""
        for callback in self.state_exit_callbacks[state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state, self.state_data)
                else:
                    callback(state, self.state_data)
            except Exception as e:
                self.logger.error(f"Error in exit callback: {e}", state=state.value)
    
    async def _execute_enter_callbacks(self, state: SystemState) -> None:
        """Execute enter callbacks for a state"""
        for callback in self.state_enter_callbacks[state]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state, self.state_data)
                else:
                    callback(state, self.state_data)
            except Exception as e:
                self.logger.error(f"Error in enter callback: {e}", state=state.value)
    
    async def _execute_transition_callbacks(self, transition_record: Dict[str, Any]) -> None:
        """Execute transition callbacks"""
        for callback in self.transition_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(transition_record)
                else:
                    callback(transition_record)
            except Exception as e:
                self.logger.error(f"Error in transition callback: {e}")
    
    async def _setup_state_timeout(self, state: SystemState) -> None:
        """Configure timeout for a state"""
        if state in self.state_timeouts:
            timeout_seconds = self.state_timeouts[state]
            self._timeout_task = asyncio.create_task(
                self._handle_state_timeout(state, timeout_seconds)
            )
    
    async def _handle_state_timeout(self, state: SystemState, timeout_seconds: int) -> None:
        """Handle state timeout"""
        try:
            await asyncio.sleep(timeout_seconds)
            
            # Verify we're still in the same state
            if self.current_state == state:
                self.logger.warning(
                    f"Timeout in state {state.value}",
                    timeout_seconds=timeout_seconds
                )
                
                # Automatic transition to IDLE on timeout
                await self.transition_to(SystemState.IDLE, trigger="timeout")
                
        except asyncio.CancelledError:
            # Timeout cancelled by normal transition
            pass
        except Exception as e:
            self.logger.error(f"Error in state timeout: {e}", state=state.value)
    
    def _should_reset_attempts(self, new_state: SystemState) -> bool:
        """Determine if attempt counters should be reset"""
        # Reset attempts when returning to IDLE or changing verification context
        if new_state == SystemState.IDLE:
            return True
        
        # Reset when changing between different verification methods
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
        """Emergency transition to error state"""
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
                "Emergency transition to error state",
                error_message=error_message,
                previous_state=self.previous_state.value if self.previous_state else None
            )
            
        except Exception as e:
            self.logger.critical(f"Critical error in emergency transition: {e}")
    
    # ==================== ATTEMPT MANAGEMENT ====================
    
    def increment_attempts(self, context: str = "default") -> int:
        """Increment attempt counter for a specific context"""
        key = f"{self.current_state.value}_{context}"
        self.attempt_counters[key] += 1
        attempts = self.attempt_counters[key]
        
        self.logger.debug(
            f"Attempts incremented in {context}",
            state=self.current_state.value,
            context=context,
            attempts=attempts
        )
        
        return attempts
    
    def get_attempts(self, context: str = "default") -> int:
        """Get current number of attempts for a context"""
        key = f"{self.current_state.value}_{context}"
        return self.attempt_counters[key]
    
    def reset_attempts(self, context: Optional[str] = None) -> None:
        """Reset attempt counters"""
        if context:
            key = f"{self.current_state.value}_{context}"
            self.attempt_counters[key] = 0
        else:
            self.attempt_counters.clear()
    
    # ==================== CALLBACK MANAGEMENT ====================
    
    def on_state_enter(self, state: SystemState, callback: Callable) -> None:
        """Register a callback for when entering a state"""
        self.state_enter_callbacks[state].append(callback)
    
    def on_state_exit(self, state: SystemState, callback: Callable) -> None:
        """Register a callback for when exiting a state"""
        self.state_exit_callbacks[state].append(callback)
    
    def on_transition(self, callback: Callable) -> None:
        """Register a callback for any transition"""
        self.transition_callbacks.append(callback)
    
    # ==================== INFORMATION AND STATE ====================
    
    def get_current_state(self) -> SystemState:
        """Get current state"""
        return self.current_state
    
    def get_state_data(self) -> StateData:
        """Get current state data"""
        return self.state_data
    
    def get_state_duration(self) -> float:
        """Get current state duration in seconds"""
        return (datetime.now() - self.state_start_time).total_seconds()
    
    def get_last_activity_time(self) -> datetime:
        """Get last activity timestamp"""
        return self.last_activity_time
    
    def update_activity(self) -> None:
        """Update last activity timestamp"""
        self.last_activity_time = datetime.now()
    
    def is_in_verification_state(self) -> bool:
        """Determine if we're in a verification state"""
        verification_states = {
            SystemState.FACIAL_RECOGNITION,
            SystemState.FINGERPRINT_VERIFICATION,
            SystemState.MANUAL_ENTRY
        }
        return self.current_state in verification_states
    
    def is_idle(self) -> bool:
        """Determine if we're in IDLE state"""
        return self.current_state == SystemState.IDLE
    
    def can_transition_to(self, state: SystemState) -> bool:
        """Check if a transition is valid"""
        return state in self.valid_transitions[self.current_state]
    
    def get_state_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get state history"""
        if limit:
            return self.state_history[-limit:]
        return self.state_history.copy()
    
    def get_state_statistics(self) -> Dict[str, Any]:
        """Get state manager statistics"""
        # Count time per state
        state_durations = defaultdict(float)
        for record in self.state_history:
            state_durations[record["from_state"]] += record["duration_seconds"]
        
        # Count transitions
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
    
    # ==================== UTILITIES FOR TESTING ====================
    
    def force_state(self, state: SystemState, data: Optional[StateData] = None) -> None:
        """
        Force a state without validations (only for testing).
        DO NOT USE IN PRODUCTION!
        """
        if not self.config.is_mock_mode():
            raise StateManagerError("force_state only available in mock mode")
        
        self.logger.warning(
            "Forcing state (testing mode)",
            from_state=self.current_state.value,
            to_state=state.value
        )
        
        self.previous_state = self.current_state
        self.current_state = state
        self.state_data = data or StateData()
        self.state_start_time = datetime.now()
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information from state manager"""
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


# Global state manager instance
_state_manager = None


def get_state_manager() -> StateManager:
    """Get global state manager instance"""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


# Convenience functions for common use
async def transition_to_idle(trigger: str = "manual") -> bool:
    """Quick transition to IDLE state"""
    return await get_state_manager().transition_to(SystemState.IDLE, trigger)


async def transition_to_error(error_message: str) -> bool:
    """Quick transition to ERROR state"""
    error_data = StateData(
        error_info={
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }
    )
    return await get_state_manager().transition_to(SystemState.ERROR, "error", error_data)


def get_current_state() -> SystemState:
    """Get current state"""
    return get_state_manager().get_current_state()


def is_in_verification_state() -> bool:
    """Determine if we're in a verification state"""
    return get_state_manager().is_in_verification_state()


if __name__ == "__main__":
    # Basic state manager test
    async def test_state_manager():
        sm = get_state_manager()
        
        print(f"Initial state: {sm.get_current_state().value}")
        
        # Test valid transition
        success = await sm.transition_to(SystemState.ACTIVATION, "test_trigger")
        print(f"Transition to ACTIVATION: {'successful' if success else 'failed'}")
        print(f"Current state: {sm.get_current_state().value}")
        
        # Test invalid transition
        try:
            await sm.transition_to(SystemState.CONFIRMATION, "invalid_trigger")
        except InvalidStateTransitionError as e:
            print(f"Invalid transition detected: {e}")
        
        # Test attempt increment
        attempts = sm.increment_attempts("facial")
        print(f"Facial recognition attempts: {attempts}")
        
        # Test statistics
        stats = sm.get_state_statistics()
        print(f"Statistics: {stats}")
        
        # Test callback
        def on_enter_idle(state, data):
            print(f"Callback: Entering state {state.value}")
        
        sm.on_state_enter(SystemState.IDLE, on_enter_idle)
        
        # Return to IDLE
        await sm.transition_to(SystemState.IDLE, "test_complete")
        
        # Test timeout
        await sm.transition_to(SystemState.FACIAL_RECOGNITION, "timeout_test")
        print("Waiting for timeout...")
        await asyncio.sleep(2)
        print(f"State after timeout: {sm.get_current_state().value}")
        
        # Debug info
        debug = sm.get_debug_info()
        print(f"Debug info: {debug}")
    
    asyncio.run(test_state_manager())