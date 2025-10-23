"""
Critical path tests for autoD.

This package contains tests for the most critical code paths that must
work correctly for the system to function properly:

- Circuit breaker state machine (api_client.py)
- Retry logic edge cases
- Error injection and recovery
- Database transaction handling
- Processor error paths

These tests focus on error handling, edge cases, and failure scenarios
that are not covered by standard happy-path integration tests.
"""
