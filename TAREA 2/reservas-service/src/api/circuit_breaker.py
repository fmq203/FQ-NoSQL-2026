"""Circuit breaker middleware for HTTP clients."""
import time
import logging
from enum import Enum
from typing import Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        half_open_timeout: int = 30,
        success_threshold: int = 1
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.half_open_timeout = half_open_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0
        self.last_failure_time: Optional[float] = None
    
    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed to move to half-open
            if self.last_failure_time and time.time() - self.last_failure_time >= 30:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        
        # HALF_OPEN allows one request
        return True
    
    def record_success(self) -> None:
        """Record successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= 1:  # success_threshold
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.successes = 0
        elif self.state == CircuitState.CLOSED:
            self.failures = 0
    
    def record_failure(self) -> None:
        """Record failed execution."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.successes = 0
        elif self.state == CircuitState.CLOSED and self.failures >= 5:  # failure_threshold
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN for {self.name}")
    
    def get_state(self) -> str:
        return self.state.value


# Global circuit breakers
_circuit_breakers: Dict[str, CircuitBreaker] = {
    "usuarios": CircuitBreaker("usuarios"),
    "eventos": CircuitBreaker("eventos"),
}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name)
    return _circuit_breakers[name]


def can_call_service(service: str) -> bool:
    """Check if service call is allowed."""
    cb = get_circuit_breaker(service)
    return cb.can_execute()


def record_service_call(service: str, success: bool) -> None:
    """Record service call result."""
    cb = get_circuit_breaker(service)
    if success:
        cb.record_success()
    else:
        cb.record_failure()


def get_all_circuit_states() -> Dict[str, str]:
    """Get all circuit breaker states."""
    return {name: cb.get_state() for name, cb in _circuit_breakers.items()}