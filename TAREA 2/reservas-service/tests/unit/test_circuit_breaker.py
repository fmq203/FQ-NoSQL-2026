"""Circuit breaker state transition tests."""
import pytest
import time
from src.api.circuit_breaker import CircuitBreaker, CircuitState, get_circuit_breaker, _circuit_breakers


def reset_circuit_breakers():
    """Reset global circuit breakers to initial state."""
    global _circuit_breakers
    _circuit_breakers.clear()
    _circuit_breakers["usuarios"] = CircuitBreaker("usuarios")
    _circuit_breakers["eventos"] = CircuitBreaker("eventos")


class TestCircuitBreakerTransitions:
    """Tests for circuit breaker state transitions."""

    def setup_method(self):
        """Reset circuit breakers before each test."""
        reset_circuit_breakers()

    def test_initial_state_closed(self):
        """New circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker("test")
        assert cb.get_state() == "closed"

    def test_opens_after_failure_threshold(self):
        """Circuit should open after 5 consecutive failures."""
        cb = CircuitBreaker("test", failure_threshold=3)
        
        # Record failures
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == "closed"  # Still closed
        
        cb.record_failure()
        assert cb.get_state() == "open"  # Opens after 3 failures

    def test_half_open_after_timeout(self):
        """Circuit should transition to half-open after timeout."""
        cb = CircuitBreaker("test", failure_threshold=2, half_open_timeout=1)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == "open"
        
        # Manually set last_failure_time to simulate timeout passage
        cb.last_failure_time = time.time() - 2
        
        # Next can_execute should transition to half-open
        assert cb.can_execute() is True
        assert cb.get_state() == "half-open"

    def test_closes_after_success_in_half_open(self):
        """Circuit should close after successful request in half-open."""
        cb = CircuitBreaker("test", failure_threshold=2, half_open_timeout=1)
        
        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == "open"
        
        # Force to half-open by manipulating time
        cb.last_failure_time = time.time() - 2
        assert cb.can_execute() is True
        assert cb.get_state() == "half-open"
        
        # Success should close it
        cb.record_success()
        assert cb.get_state() == "closed"

    def test_reopens_on_failure_in_half_open(self):
        """Circuit should reopen on failure in half-open state."""
        cb = CircuitBreaker("test", failure_threshold=2, half_open_timeout=1)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == "open"
        
        # Force half-open
        cb.last_failure_time = time.time() - 2
        assert cb.can_execute() is True
        assert cb.get_state() == "half-open"
        
        # Failure should reopen
        cb.record_failure()
        assert cb.get_state() == "open"

    def test_success_resets_failures_in_closed(self):
        """Success in closed state resets failure count."""
        cb = CircuitBreaker("test", failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        assert cb.failures == 2
        
        cb.record_success()
        assert cb.failures == 0  # Reset

    def test_global_circuit_breakers_initialization(self):
        """Global circuit breakers should be initialized."""
        from src.api.circuit_breaker import _circuit_breakers
        
        assert "usuarios" in _circuit_breakers
        assert "eventos" in _circuit_breakers
        
        for cb in _circuit_breakers.values():
            assert cb.get_state() == "closed"

    def test_get_all_circuit_states(self):
        """get_all_circuit_states should return all states."""
        from src.api.circuit_breaker import get_all_circuit_states
        
        states = get_all_circuit_states()
        
        assert "usuarios" in states
        assert "eventos" in states
        assert states["usuarios"] == "closed"
        assert states["eventos"] == "closed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])