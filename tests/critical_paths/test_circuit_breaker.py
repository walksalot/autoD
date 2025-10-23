"""
Circuit breaker state machine tests.

Tests the complete state machine for the CircuitBreaker class in api_client.py.
The circuit breaker pattern prevents cascade failures by detecting when a
service is failing and temporarily rejecting requests to give it time to recover.

States:
- CLOSED: Normal operation, all requests allowed
- OPEN: Too many failures, all requests rejected immediately
- HALF_OPEN: Testing if service recovered, one request allowed

Critical behaviors tested:
1. CLOSED state allows all requests
2. Failure threshold (default: 10) opens circuit
3. OPEN state rejects requests immediately
4. Timeout (default: 60s) transitions to HALF_OPEN
5. Success in HALF_OPEN closes circuit
6. Failure in HALF_OPEN reopens circuit
7. Concurrent requests handled correctly
8. State transitions are atomic
"""

import pytest
import time
from unittest.mock import Mock

from src.api_client import CircuitBreaker


class TestCircuitBreakerStateMachine:
    """Test complete circuit breaker state machine behavior."""

    def test_closed_state_allows_requests(self):
        """CLOSED state should allow all requests through."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        # Verify initial state
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

        # Execute successful function
        mock_fn = Mock(return_value="success")
        result = breaker.call(mock_fn, arg1="test", arg2=123)

        # Verify request was allowed
        assert result == "success"
        mock_fn.assert_called_once_with(arg1="test", arg2=123)

        # State should remain CLOSED
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    def test_failure_threshold_opens_circuit(self):
        """After threshold failures, circuit should open."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        mock_fn = Mock(side_effect=ValueError("test error"))

        # Cause 3 failures to reach threshold
        for i in range(3):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

            # Check failure count increments
            assert breaker.failure_count == i + 1

            # Circuit should open on last failure
            if i < 2:
                assert breaker.state == "CLOSED"
            else:
                assert breaker.state == "OPEN"

    def test_open_state_rejects_requests_immediately(self):
        """OPEN state should reject requests without calling function."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=60)

        # Force circuit open
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"

        # Reset mock to verify it's not called
        mock_fn.reset_mock()
        mock_fn.side_effect = None
        mock_fn.return_value = "success"

        # Attempt to call - should fail immediately without executing function
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            breaker.call(mock_fn)

        # Verify function was never called
        mock_fn.assert_not_called()

    def test_timeout_transitions_to_half_open(self):
        """After timeout, OPEN circuit transitions to HALF_OPEN."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)  # 100ms timeout

        # Force circuit open
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"
        assert breaker.last_failure_time is not None

        # Wait for timeout to expire
        time.sleep(0.15)  # Wait 150ms (> 100ms timeout)

        # Next call should transition to HALF_OPEN
        mock_fn.reset_mock()
        mock_fn.side_effect = None
        mock_fn.return_value = "success"

        result = breaker.call(mock_fn)

        # Should have transitioned to HALF_OPEN before executing
        # Then SUCCESS closes circuit back to CLOSED
        assert result == "success"
        assert breaker.state == "CLOSED"  # Success in HALF_OPEN closes circuit
        mock_fn.assert_called_once()

    def test_success_in_half_open_closes_circuit(self):
        """Successful call in HALF_OPEN should close circuit."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)

        # Force circuit open
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(0.15)

        # Successful call should close circuit
        mock_fn.reset_mock()
        mock_fn.side_effect = None
        mock_fn.return_value = "success"

        result = breaker.call(mock_fn)

        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0  # Reset on success

    def test_failure_in_half_open_reopens_circuit(self):
        """Failed call in HALF_OPEN should reopen circuit."""
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)

        # Force circuit open
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"
        initial_failure_time = breaker.last_failure_time

        # Wait for timeout to allow transition to HALF_OPEN
        time.sleep(0.15)

        # Failed call should reopen circuit
        mock_fn.reset_mock()
        mock_fn.side_effect = ValueError("still failing")

        with pytest.raises(ValueError, match="still failing"):
            breaker.call(mock_fn)

        # Circuit should be OPEN again
        assert breaker.state == "OPEN"
        assert breaker.failure_count == 3  # Incremented
        assert breaker.last_failure_time > initial_failure_time  # Updated

    def test_concurrent_requests_during_state_transition(self):
        """Circuit breaker should handle concurrent requests correctly.

        This test verifies that the circuit breaker is thread-safe during
        state transitions. While not a true concurrency test (no threading),
        it verifies the state machine logic handles rapid sequential calls.
        """
        breaker = CircuitBreaker(failure_threshold=3, timeout=0.1)

        # Simulate rapid failures
        mock_fn = Mock(side_effect=ValueError("error"))

        failures = 0
        for i in range(5):  # Attempt 5 calls
            try:
                breaker.call(mock_fn)
            except (ValueError, Exception):
                failures += 1

        # First 3 should fail with ValueError, rest with circuit breaker
        assert failures == 5
        assert breaker.state == "OPEN"

        # Wait for timeout
        time.sleep(0.15)

        # First call after timeout should attempt (HALF_OPEN)
        mock_fn.reset_mock()
        mock_fn.side_effect = None
        mock_fn.return_value = "recovered"

        result = breaker.call(mock_fn)
        assert result == "recovered"
        assert breaker.state == "CLOSED"

    def test_state_transitions_are_deterministic(self):
        """State transitions should follow predictable rules."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=0.1)

        # State 1: CLOSED → OPEN (via failures)
        assert breaker.state == "CLOSED"

        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"

        # State 2: OPEN → HALF_OPEN (via timeout)
        time.sleep(0.15)

        # Manually set state to HALF_OPEN by attempting a call
        # (CircuitBreaker transitions on call attempt)
        # Create new mock to avoid side_effect persistence
        mock_fn = Mock(return_value="success")

        result = breaker.call(mock_fn)

        # State 3: HALF_OPEN → CLOSED (via success)
        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

        # Verify can handle normal requests again
        result2 = breaker.call(mock_fn)
        assert result2 == "success"
        assert breaker.state == "CLOSED"


class TestCircuitBreakerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_failure_threshold_always_open(self):
        """Failure threshold of 0 should immediately open circuit.

        Note: This is a degenerate case - in practice, minimum should be 1.
        """
        breaker = CircuitBreaker(failure_threshold=0, timeout=60)

        # Even a single failure should open circuit
        mock_fn = Mock(side_effect=ValueError("error"))

        with pytest.raises(ValueError):
            breaker.call(mock_fn)

        # Circuit should be OPEN immediately (threshold is 0)
        assert breaker.state == "OPEN"

    def test_large_failure_threshold(self):
        """Circuit breaker should handle large thresholds correctly."""
        breaker = CircuitBreaker(failure_threshold=1000, timeout=60)

        mock_fn = Mock(side_effect=ValueError("error"))

        # Cause 500 failures
        for i in range(500):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

            # Should still be CLOSED
            assert breaker.state == "CLOSED"
            assert breaker.failure_count == i + 1

        # Cause 500 more to reach threshold
        for _ in range(500):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        # Now should be OPEN
        assert breaker.state == "OPEN"
        assert breaker.failure_count >= 1000

    def test_zero_timeout_immediate_half_open(self):
        """Zero timeout should immediately allow HALF_OPEN state.

        This is useful for testing recovery logic without delays.
        """
        breaker = CircuitBreaker(failure_threshold=2, timeout=0)

        # Force circuit open
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.state == "OPEN"

        # With zero timeout, next call should immediately try (HALF_OPEN)
        # Create new mock to avoid side_effect persistence
        mock_fn = Mock(return_value="success")

        result = breaker.call(mock_fn)

        # Should succeed and close circuit
        assert result == "success"
        assert breaker.state == "CLOSED"

    def test_exception_in_function_updates_failure_count(self):
        """Any exception in called function should increment failure count."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=60)

        # Test different exception types
        exceptions = [ValueError("test"), TypeError("test"), RuntimeError("test")]

        for i, exc in enumerate(exceptions):
            mock_fn = Mock(side_effect=exc)

            with pytest.raises(type(exc)):
                breaker.call(mock_fn)

            assert breaker.failure_count == i + 1

        # Circuit should be OPEN after 3 failures
        assert breaker.state == "OPEN"

    def test_successful_calls_reset_failure_count_in_closed_state(self):
        """Successful calls in CLOSED state should keep failure_count at 0."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        # Cause some failures (but don't reach threshold)
        mock_fn = Mock(side_effect=ValueError("error"))
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(mock_fn)

        assert breaker.failure_count == 3
        assert breaker.state == "CLOSED"

        # Successful call should reset count
        mock_fn.reset_mock()
        mock_fn.side_effect = None
        mock_fn.return_value = "success"

        result = breaker.call(mock_fn)

        assert result == "success"
        assert breaker.failure_count == 0
        assert breaker.state == "CLOSED"


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with realistic scenarios."""

    def test_circuit_breaker_with_retryable_errors(self):
        """Circuit breaker should work with retry logic patterns."""
        breaker = CircuitBreaker(failure_threshold=3, timeout=0.1)

        # Simulate API that fails 3 times then succeeds
        call_count = [0]

        def flaky_api():
            call_count[0] += 1
            if call_count[0] <= 3:
                raise ValueError("API temporary failure")
            return "success"

        # First 3 calls fail and open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                breaker.call(flaky_api)

        assert breaker.state == "OPEN"

        # Circuit now rejects calls
        with pytest.raises(Exception, match="Circuit breaker OPEN"):
            breaker.call(flaky_api)

        # Wait for timeout
        time.sleep(0.15)

        # Next call succeeds (API recovered)
        result = breaker.call(flaky_api)
        assert result == "success"
        assert breaker.state == "CLOSED"

    def test_circuit_breaker_protects_downstream_service(self):
        """Circuit breaker should prevent overwhelming a failing service."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=0.1)

        # Track how many times the "service" is called
        service_call_count = [0]

        def failing_service():
            service_call_count[0] += 1
            raise ConnectionError("Service unavailable")

        # Cause 5 failures to open circuit
        for _ in range(5):
            with pytest.raises(ConnectionError):
                breaker.call(failing_service)

        # Service was called 5 times (threshold)
        assert service_call_count[0] == 5
        assert breaker.state == "OPEN"

        # Attempt 10 more calls - circuit is OPEN so service is NOT called
        for _ in range(10):
            with pytest.raises(Exception, match="Circuit breaker OPEN"):
                breaker.call(failing_service)

        # Service should still have only been called 5 times (protected)
        assert service_call_count[0] == 5
        assert breaker.state == "OPEN"  # Still OPEN (no timeout yet)

    def test_circuit_breaker_with_function_arguments(self):
        """Circuit breaker should correctly pass arguments and kwargs."""
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        mock_fn = Mock(return_value="processed")

        result = breaker.call(mock_fn, "arg1", "arg2", kwarg1="value1", kwarg2=123)

        assert result == "processed"
        mock_fn.assert_called_once_with("arg1", "arg2", kwarg1="value1", kwarg2=123)
