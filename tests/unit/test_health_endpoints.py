"""
Unit tests for health check endpoints.

Tests cover:
- Liveness probe functionality
- Readiness probe with dependency checks
- Startup probe with initialization state
- Detailed dependency status reporting
- Response time validation (<100ms target)
- Error handling and edge cases
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from src.health_endpoints import (
    app,
    mark_initialization_complete,
    check_database_health,
    check_openai_health,
    check_vector_store_health,
    DependencyStatus,
)


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_initialization():
    """Reset initialization state before each test."""
    import src.health_endpoints as health_module

    health_module._initialization_complete = False
    health_module._start_time = time.time()
    yield
    # Cleanup after test
    health_module._initialization_complete = False


class TestLivenessProbe:
    """Test liveness probe endpoint."""

    def test_liveness_returns_200(self, client):
        """Test that liveness probe returns 200."""
        response = client.get("/health/live")

        assert response.status_code == 200

    def test_liveness_response_structure(self, client):
        """Test liveness response has correct structure."""
        response = client.get("/health/live")
        data = response.json()

        assert "status" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data

        assert data["status"] == "alive"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_liveness_timestamp_format(self, client):
        """Test timestamp is ISO 8601 format."""
        response = client.get("/health/live")
        data = response.json()

        # Check timestamp ends with Z (UTC)
        assert data["timestamp"].endswith("Z")

        # Verify it can be parsed
        from datetime import datetime

        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_liveness_response_time(self, client):
        """Test liveness probe responds quickly (<100ms)."""
        start = time.time()
        response = client.get("/health/live")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert (
            elapsed_ms < 100
        ), f"Liveness probe took {elapsed_ms:.2f}ms (target: <100ms)"


class TestReadinessProbe:
    """Test readiness probe endpoint."""

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    def test_readiness_healthy_dependencies(self, mock_openai, mock_db, client):
        """Test readiness returns 200 when all dependencies healthy."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=10.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=50.0
        )

        response = client.get("/health/ready")
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "ready"

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    def test_readiness_unhealthy_database(self, mock_openai, mock_db, client):
        """Test readiness returns 503 when database unhealthy."""
        mock_db.return_value = DependencyStatus(
            name="database",
            healthy=False,
            response_time_ms=10.0,
            error="Connection refused",
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=50.0
        )

        response = client.get("/health/ready")
        data = response.json()

        assert response.status_code == 503
        assert data["status"] == "not_ready"

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    def test_readiness_unhealthy_openai(self, mock_openai, mock_db, client):
        """Test readiness returns 503 when OpenAI API unhealthy."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=10.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api",
            healthy=False,
            response_time_ms=5000.0,
            error="Timeout",
        )

        response = client.get("/health/ready")
        data = response.json()

        assert response.status_code == 503
        assert data["status"] == "not_ready"

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    def test_readiness_all_unhealthy(self, mock_openai, mock_db, client):
        """Test readiness when all dependencies unhealthy."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=False, response_time_ms=10.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=False, response_time_ms=50.0
        )

        response = client.get("/health/ready")

        assert response.status_code == 503


class TestStartupProbe:
    """Test startup probe endpoint."""

    def test_startup_not_complete(self, client):
        """Test startup probe returns 503 before initialization."""
        response = client.get("/health/startup")
        data = response.json()

        assert response.status_code == 503
        assert data["status"] == "starting"

    def test_startup_complete(self, client):
        """Test startup probe returns 200 after initialization."""
        mark_initialization_complete()

        response = client.get("/health/startup")
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "started"

    def test_startup_uptime_increments(self, client):
        """Test uptime increases over time."""
        response1 = client.get("/health/startup")
        uptime1 = response1.json()["uptime_seconds"]

        time.sleep(0.1)

        response2 = client.get("/health/startup")
        uptime2 = response2.json()["uptime_seconds"]

        assert uptime2 > uptime1


class TestDependencyStatus:
    """Test detailed dependency status endpoint."""

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    @patch("src.health_endpoints.check_vector_store_health")
    def test_dependency_status_all_healthy(
        self, mock_vector, mock_openai, mock_db, client
    ):
        """Test dependency status when all healthy."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=5.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=50.0
        )
        mock_vector.return_value = DependencyStatus(
            name="vector_store", healthy=True, response_time_ms=100.0
        )

        response = client.get("/health/dependencies")
        data = response.json()

        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["overall_healthy"] is True
        assert len(data["dependencies"]) == 3

        # Verify each dependency
        dep_names = [d["name"] for d in data["dependencies"]]
        assert "database" in dep_names
        assert "openai_api" in dep_names
        assert "vector_store" in dep_names

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    @patch("src.health_endpoints.check_vector_store_health")
    def test_dependency_status_vector_store_degraded(
        self, mock_vector, mock_openai, mock_db, client
    ):
        """Test that vector store degraded doesn't affect overall health."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=5.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=50.0
        )
        mock_vector.return_value = DependencyStatus(
            name="vector_store",
            healthy=False,
            response_time_ms=1000.0,
            error="Vector store unavailable",
        )

        response = client.get("/health/dependencies")
        data = response.json()

        # Overall should still be healthy (vector store is non-critical)
        assert data["overall_healthy"] is True
        assert data["status"] == "healthy"

        # But vector_store should show as unhealthy
        vector_dep = next(
            d for d in data["dependencies"] if d["name"] == "vector_store"
        )
        assert vector_dep["healthy"] is False

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    @patch("src.health_endpoints.check_vector_store_health")
    def test_dependency_response_times_included(
        self, mock_vector, mock_openai, mock_db, client
    ):
        """Test that response times are included for each dependency."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=12.5
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=75.3
        )
        mock_vector.return_value = DependencyStatus(
            name="vector_store", healthy=True, response_time_ms=150.7
        )

        response = client.get("/health/dependencies")
        data = response.json()

        for dep in data["dependencies"]:
            assert "response_time_ms" in dep
            assert dep["response_time_ms"] is not None
            assert dep["response_time_ms"] > 0


class TestDatabaseHealthCheck:
    """Test database health check function."""

    @patch("src.health_endpoints.DatabaseManager")
    def test_database_healthy(self, mock_db_manager):
        """Test database health check when healthy."""
        mock_instance = MagicMock()
        mock_instance.health_check.return_value = True
        mock_db_manager.return_value = mock_instance

        status = check_database_health()

        assert status.name == "database"
        assert status.healthy is True
        assert status.error is None
        assert status.response_time_ms is not None

    @patch("src.health_endpoints.DatabaseManager")
    def test_database_unhealthy(self, mock_db_manager):
        """Test database health check when unhealthy."""
        mock_instance = MagicMock()
        mock_instance.health_check.return_value = False
        mock_db_manager.return_value = mock_instance

        status = check_database_health()

        assert status.name == "database"
        assert status.healthy is False
        assert status.error is not None

    @patch("src.health_endpoints.DatabaseManager")
    def test_database_exception(self, mock_db_manager):
        """Test database health check when exception occurs."""
        mock_db_manager.side_effect = Exception("Connection failed")

        status = check_database_health()

        assert status.name == "database"
        assert status.healthy is False
        assert "Connection failed" in status.error


class TestOpenAIHealthCheck:
    """Test OpenAI API health check function."""

    @patch("openai.OpenAI")
    def test_openai_healthy(self, mock_openai_class):
        """Test OpenAI health check when healthy."""
        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_models.data = [{"id": "gpt-5-mini"}]
        mock_client.models.list.return_value = mock_models
        mock_openai_class.return_value = mock_client

        status = check_openai_health()

        assert status.name == "openai_api"
        assert status.healthy is True
        assert status.error is None

    @patch("openai.OpenAI")
    def test_openai_exception(self, mock_openai_class):
        """Test OpenAI health check when exception occurs."""
        mock_openai_class.side_effect = Exception("API timeout")

        status = check_openai_health()

        assert status.name == "openai_api"
        assert status.healthy is False
        assert "API timeout" in status.error


class TestVectorStoreHealthCheck:
    """Test vector store health check function."""

    @patch("src.health_endpoints.VectorStoreManager")
    def test_vector_store_healthy(self, mock_manager_class):
        """Test vector store health check when healthy."""
        mock_manager = MagicMock()
        mock_manager.get_or_create_vector_store.return_value = MagicMock(id="vs-123")
        mock_manager.vector_store_name = "test_store"
        mock_manager._vector_store_id = "vs-123"
        mock_manager_class.return_value = mock_manager

        status = check_vector_store_health()

        assert status.name == "vector_store"
        assert status.healthy is True

    @patch("src.health_endpoints.VectorStoreManager")
    def test_vector_store_exception(self, mock_manager_class):
        """Test vector store health check when exception occurs."""
        mock_manager_class.side_effect = Exception("Network error")

        status = check_vector_store_health()

        assert status.name == "vector_store"
        assert status.healthy is False
        assert "Network error" in status.error


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_returns_service_info(self, client):
        """Test root endpoint returns service information."""
        response = client.get("/")
        data = response.json()

        assert response.status_code == 200
        assert "service" in data
        assert "version" in data
        assert "endpoints" in data

        # Verify all health endpoints are listed
        endpoints = data["endpoints"]
        assert "/health/live" in endpoints.values()
        assert "/health/ready" in endpoints.values()
        assert "/health/startup" in endpoints.values()
        assert "/health/dependencies" in endpoints.values()


class TestPerformanceRequirements:
    """Test performance requirements for health checks."""

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    def test_readiness_response_time(self, mock_openai, mock_db, client):
        """Test readiness probe completes in <100ms."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=5.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=10.0
        )

        start = time.time()
        response = client.get("/health/ready")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        assert (
            elapsed_ms < 100
        ), f"Readiness probe took {elapsed_ms:.2f}ms (target: <100ms)"

    @patch("src.health_endpoints.check_database_health")
    @patch("src.health_endpoints.check_openai_health")
    @patch("src.health_endpoints.check_vector_store_health")
    def test_dependency_status_response_time(
        self, mock_vector, mock_openai, mock_db, client
    ):
        """Test dependency status completes in reasonable time."""
        mock_db.return_value = DependencyStatus(
            name="database", healthy=True, response_time_ms=5.0
        )
        mock_openai.return_value = DependencyStatus(
            name="openai_api", healthy=True, response_time_ms=10.0
        )
        mock_vector.return_value = DependencyStatus(
            name="vector_store", healthy=True, response_time_ms=15.0
        )

        start = time.time()
        response = client.get("/health/dependencies")
        elapsed_ms = (time.time() - start) * 1000

        assert response.status_code == 200
        # Allow more time for detailed check (200ms)
        assert (
            elapsed_ms < 200
        ), f"Dependency check took {elapsed_ms:.2f}ms (target: <200ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
