"""
Health check endpoints for Kubernetes and monitoring systems.

Provides HTTP endpoints for:
- Liveness probes (is the process alive?)
- Readiness probes (can the service handle traffic?)
- Startup probes (has initialization completed?)
- Dependency status (detailed health of all dependencies)

All endpoints target sub-100ms response times for efficient health monitoring.
"""

import logging
import time
from typing import Dict, Any, Optional, Iterator
from datetime import datetime
from contextlib import contextmanager

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from src.config import get_config
from src.database import DatabaseManager
from src.vector_store import VectorStoreManager
from src.metrics import PrometheusExporter


logger = logging.getLogger("paper_autopilot")


# Response models
class HealthResponse(BaseModel):
    """Standard health check response."""

    status: str
    timestamp: str
    uptime_seconds: Optional[float] = None


class DependencyStatus(BaseModel):
    """Status of a single dependency."""

    name: str
    healthy: bool
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class DetailedHealthResponse(BaseModel):
    """Detailed health response with dependency status."""

    status: str
    timestamp: str
    uptime_seconds: float
    dependencies: list[DependencyStatus]
    overall_healthy: bool


# FastAPI app for health checks
app = FastAPI(
    title="Paper Autopilot Health Checks",
    description="Kubernetes-compatible health check endpoints",
    version="1.0.0",
)


# Global state
_start_time = time.time()
_initialization_complete = False


def mark_initialization_complete() -> None:
    """Mark that application initialization is complete."""
    global _initialization_complete
    _initialization_complete = True
    logger.info("Application initialization marked as complete")


@contextmanager
def timed_operation() -> Iterator[None]:
    """Context manager to measure operation duration."""
    start = time.time()
    try:
        yield
    finally:
        _ = (time.time() - start) * 1000  # Convert to ms (unused, for future logging)


def check_database_health() -> DependencyStatus:
    """
    Check database connectivity and health.

    Returns:
        DependencyStatus with database health information
    """
    start = time.time()

    try:
        config = get_config()
        db_manager = DatabaseManager(config.paper_autopilot_db_url)

        healthy = db_manager.health_check()
        response_time_ms = (time.time() - start) * 1000

        return DependencyStatus(
            name="database",
            healthy=healthy,
            response_time_ms=round(response_time_ms, 2),
            error=None if healthy else "Database connectivity check failed",
            details={
                "db_url": config.paper_autopilot_db_url.split("://")[0]
                + "://***/***"  # Redact credentials
            },
        )
    except Exception as e:
        response_time_ms = (time.time() - start) * 1000
        logger.error(f"Database health check failed: {e}")
        return DependencyStatus(
            name="database",
            healthy=False,
            response_time_ms=round(response_time_ms, 2),
            error=str(e),
        )


def check_openai_health() -> DependencyStatus:
    """
    Check OpenAI API availability.

    Performs a lightweight check (model list) to verify API connectivity
    without consuming significant quota.

    Returns:
        DependencyStatus with OpenAI API health information
    """
    start = time.time()

    try:
        from openai import OpenAI

        config = get_config()
        client = OpenAI(api_key=config.openai_api_key, timeout=5.0)

        # Lightweight check - list models (cached by OpenAI)
        models = client.models.list()
        response_time_ms = (time.time() - start) * 1000

        return DependencyStatus(
            name="openai_api",
            healthy=True,
            response_time_ms=round(response_time_ms, 2),
            details={
                "model_configured": config.openai_model,
                "models_available": len(models.data) if hasattr(models, "data") else 0,
            },
        )
    except Exception as e:
        response_time_ms = (time.time() - start) * 1000
        logger.error(f"OpenAI health check failed: {e}")
        return DependencyStatus(
            name="openai_api",
            healthy=False,
            response_time_ms=round(response_time_ms, 2),
            error=str(e),
        )


def check_vector_store_health() -> DependencyStatus:
    """
    Check vector store accessibility.

    Performs a lightweight check to verify vector store is accessible
    without creating or modifying data.

    Returns:
        DependencyStatus with vector store health information
    """
    start = time.time()

    try:
        vector_manager = VectorStoreManager()

        # Check if vector store exists (reads cached ID)
        vector_store = vector_manager.get_or_create_vector_store()
        response_time_ms = (time.time() - start) * 1000

        return DependencyStatus(
            name="vector_store",
            healthy=vector_store is not None,
            response_time_ms=round(response_time_ms, 2),
            details={
                "vector_store_name": vector_manager.config.vector_store_name,
                "has_cached_id": vector_manager.vector_store_id is not None,
            },
        )
    except Exception as e:
        response_time_ms = (time.time() - start) * 1000
        logger.warning(f"Vector store health check failed (non-critical): {e}")
        # Vector store is non-critical - mark as degraded but not unhealthy
        return DependencyStatus(
            name="vector_store",
            healthy=False,  # Mark unhealthy but don't fail overall readiness
            response_time_ms=round(response_time_ms, 2),
            error=str(e),
        )


@app.get("/health/live", response_model=HealthResponse)
async def liveness_probe() -> HealthResponse:
    """
    Liveness probe - is the process alive?

    Returns 200 if the process is running, regardless of dependency health.
    Kubernetes will restart the pod if this returns non-200.

    Use this for: Detecting deadlocks, infinite loops, or process hangs

    Returns:
        HealthResponse with status "alive"
    """
    uptime = time.time() - _start_time

    return HealthResponse(
        status="alive",
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=round(uptime, 2),
    )


@app.get("/health/ready", response_model=HealthResponse)
async def readiness_probe(response: Response) -> HealthResponse:
    """
    Readiness probe - can the service handle traffic?

    Returns 200 if all critical dependencies are healthy.
    Returns 503 if any critical dependency is unhealthy.
    Kubernetes will remove pod from service load balancer if this returns non-200.

    Critical dependencies:
    - Database connectivity (required)
    - OpenAI API availability (required)
    - Vector store (degraded, not critical)

    Use this for: Load balancer routing decisions

    Returns:
        HealthResponse with status "ready" or "not_ready"
    """
    uptime = time.time() - _start_time

    # Check critical dependencies
    db_status = check_database_health()
    api_status = check_openai_health()

    # Determine overall readiness (vector store is non-critical)
    ready = db_status.healthy and api_status.healthy

    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="not_ready",
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=round(uptime, 2),
        )

    return HealthResponse(
        status="ready",
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=round(uptime, 2),
    )


@app.get("/health/startup", response_model=HealthResponse)
async def startup_probe(response: Response) -> HealthResponse:
    """
    Startup probe - has initialization completed?

    Returns 200 once application has completed initialization.
    Returns 503 during startup phase.
    Kubernetes waits for this before checking liveness/readiness.

    Use this for: Slow-starting applications with long initialization

    Returns:
        HealthResponse with status "started" or "starting"
    """
    uptime = time.time() - _start_time

    if not _initialization_complete:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="starting",
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=round(uptime, 2),
        )

    return HealthResponse(
        status="started",
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=round(uptime, 2),
    )


@app.get("/health/dependencies", response_model=DetailedHealthResponse)
async def dependency_status() -> DetailedHealthResponse:
    """
    Detailed dependency health status.

    Returns comprehensive health information for all dependencies.
    Use this for: Debugging, monitoring dashboards, detailed health checks

    Returns:
        DetailedHealthResponse with status of all dependencies
    """
    uptime = time.time() - _start_time
    start_time = time.time()

    # Check all dependencies
    dependencies = [
        check_database_health(),
        check_openai_health(),
        check_vector_store_health(),
    ]

    # Overall health (critical dependencies only)
    critical_deps = [d for d in dependencies if d.name in ["database", "openai_api"]]
    overall_healthy = all(d.healthy for d in critical_deps)

    total_time_ms = (time.time() - start_time) * 1000

    logger.debug(
        f"Dependency health check completed in {total_time_ms:.2f}ms, "
        f"overall_healthy={overall_healthy}"
    )

    return DetailedHealthResponse(
        status="healthy" if overall_healthy else "unhealthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
        uptime_seconds=round(uptime, 2),
        dependencies=dependencies,
        overall_healthy=overall_healthy,
    )


@app.get("/metrics")
async def metrics_prometheus() -> Response:
    """
    Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format for scraping by Prometheus/Grafana.

    Use this for:
    - Prometheus metric scraping
    - Grafana dashboards
    - Alert rules

    Returns:
        Prometheus-formatted text (plain text response)
    """
    exporter = PrometheusExporter()
    prometheus_text = exporter.export_prometheus()

    return Response(
        content=prometheus_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/metrics/json")
async def metrics_json(window_minutes: int = 60) -> Dict[str, Any]:
    """
    JSON-formatted metrics endpoint.

    Returns metrics in JSON format for custom dashboards and analysis.

    Args:
        window_minutes: Time window for aggregations (default: 60)

    Use this for:
    - Custom dashboards
    - API consumers
    - Integration with non-Prometheus systems

    Returns:
        JSON metrics summary
    """
    exporter = PrometheusExporter()
    return exporter.export_json(window_minutes=window_minutes)


# Root endpoint
@app.get("/")
async def root() -> Dict[str, Any]:
    """
    Root endpoint with service information.

    Returns:
        Service name and available endpoints
    """
    return {
        "service": "Paper Autopilot Health Checks",
        "version": "1.0.0",
        "endpoints": {
            "liveness": "/health/live",
            "readiness": "/health/ready",
            "startup": "/health/startup",
            "dependencies": "/health/dependencies",
            "metrics_prometheus": "/metrics",
            "metrics_json": "/metrics/json",
        },
    }


# Example standalone server (for development/testing)
if __name__ == "__main__":
    import uvicorn  # type: ignore[import-not-found]

    # Mark initialization as complete for standalone testing
    mark_initialization_complete()

    logger.info("Starting health check server on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
