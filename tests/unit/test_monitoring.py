"""
Unit tests for monitoring infrastructure.

Tests cover:
- Metrics collection and aggregation
- Alert creation and deduplication
- Health checks and status reporting
"""

import pytest
from datetime import datetime
import json

from src.monitoring import (
    MetricsCollector,
    AlertManager,
    HealthCheck,
    AlertSeverity,
    HealthStatus,
    get_metrics_collector,
    get_alert_manager,
    get_health_check,
    record_metric,
    create_alert,
    register_health_check,
)


class TestMetricsCollector:
    """Test metrics collection and aggregation."""

    def test_record_metric(self):
        """Test recording a metric."""
        collector = MetricsCollector()

        collector.record("api.calls", 1.0, "count", {"endpoint": "/upload"})

        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "api.calls"
        assert metric.value == 1.0
        assert metric.unit == "count"
        assert metric.labels == {"endpoint": "/upload"}

    def test_get_metrics_by_name(self):
        """Test filtering metrics by name."""
        collector = MetricsCollector()

        collector.record("api.calls", 1.0)
        collector.record("api.calls", 2.0)
        collector.record("api.errors", 1.0)

        api_calls = collector.get_metrics(name="api.calls")

        assert len(api_calls) == 2
        assert all(m.name == "api.calls" for m in api_calls)

    def test_get_metrics_by_time(self):
        """Test filtering metrics by timestamp."""
        collector = MetricsCollector()

        # Record metrics
        collector.record("test", 1.0)
        old_time = datetime.now()
        collector.record("test", 2.0)

        # Get only recent metrics
        recent = collector.get_metrics(name="test", since=old_time)

        assert len(recent) == 1
        assert recent[0].value == 2.0

    def test_aggregate_metrics(self):
        """Test metric aggregation over time window."""
        collector = MetricsCollector()

        # Record test metrics
        for i in range(5):
            collector.record("response_time", float(i * 100), "ms")

        stats = collector.aggregate("response_time", window_minutes=5)

        assert stats["count"] == 5
        assert stats["sum"] == 1000.0
        assert stats["avg"] == 200.0
        assert stats["min"] == 0.0
        assert stats["max"] == 400.0

    def test_aggregate_no_metrics(self):
        """Test aggregation with no matching metrics."""
        collector = MetricsCollector()

        stats = collector.aggregate("nonexistent", window_minutes=5)

        assert stats["count"] == 0
        assert stats["sum"] == 0.0
        assert stats["avg"] == 0.0

    def test_max_metrics_limit(self):
        """Test that old metrics are trimmed."""
        collector = MetricsCollector()
        collector.max_metrics = 100

        # Record more than max
        for i in range(150):
            collector.record("test", float(i))

        assert len(collector.metrics) == 100
        # Should keep most recent
        assert collector.metrics[-1].value == 149.0

    def test_uptime_tracking(self):
        """Test system uptime tracking."""
        collector = MetricsCollector()

        uptime = collector.get_uptime_seconds()

        assert uptime >= 0.0
        assert uptime < 1.0  # Should be very recent


class TestAlertManager:
    """Test alert creation and management."""

    def test_create_alert(self, tmp_path):
        """Test creating an alert."""
        alert_file = tmp_path / "alerts.jsonl"
        manager = AlertManager(alert_file=alert_file)

        manager.create_alert(
            severity=AlertSeverity.WARNING,
            message="High error rate",
            component="api",
            details={"error_rate": 0.15},
        )

        assert len(manager.alerts) == 1
        alert = manager.alerts[0]
        assert alert.severity == AlertSeverity.WARNING
        assert alert.message == "High error rate"
        assert alert.component == "api"
        assert alert.details["error_rate"] == 0.15

    def test_alert_deduplication(self, tmp_path):
        """Test that duplicate alerts are suppressed."""
        alert_file = tmp_path / "alerts.jsonl"
        manager = AlertManager(alert_file=alert_file)

        # Create same alert twice within dedupe window
        manager.create_alert(
            AlertSeverity.WARNING,
            "Test alert",
            "test",
            dedupe_window_minutes=5,
        )
        manager.create_alert(
            AlertSeverity.WARNING,
            "Test alert",
            "test",
            dedupe_window_minutes=5,
        )

        # Should only have one alert
        assert len(manager.alerts) == 1

    def test_alert_persistence(self, tmp_path):
        """Test that alerts are persisted to disk."""
        alert_file = tmp_path / "alerts.jsonl"
        manager = AlertManager(alert_file=alert_file)

        manager.create_alert(
            AlertSeverity.ERROR,
            "Test error",
            "test",
        )

        # Check file exists and contains alert
        assert alert_file.exists()
        with open(alert_file) as f:
            alert_data = json.loads(f.readline())

        assert alert_data["message"] == "Test error"
        assert alert_data["severity"] == "error"

    def test_get_active_alerts_by_severity(self, tmp_path):
        """Test filtering alerts by severity."""
        alert_file = tmp_path / "alerts.jsonl"
        manager = AlertManager(alert_file=alert_file)

        manager.create_alert(AlertSeverity.INFO, "Info", "test")
        manager.create_alert(AlertSeverity.WARNING, "Warning", "test")
        manager.create_alert(AlertSeverity.ERROR, "Error", "test")

        errors = manager.get_active_alerts(severity=AlertSeverity.ERROR)

        assert len(errors) == 1
        assert errors[0].severity == AlertSeverity.ERROR

    def test_get_active_alerts_by_component(self, tmp_path):
        """Test filtering alerts by component."""
        alert_file = tmp_path / "alerts.jsonl"
        manager = AlertManager(alert_file=alert_file)

        manager.create_alert(AlertSeverity.ERROR, "API error", "api")
        manager.create_alert(AlertSeverity.ERROR, "DB error", "database")

        api_alerts = manager.get_active_alerts(component="api")

        assert len(api_alerts) == 1
        assert api_alerts[0].component == "api"


class TestHealthCheck:
    """Test health check system."""

    def test_register_check(self):
        """Test registering component health status."""
        health = HealthCheck()

        health.register_check("api", healthy=True)
        health.register_check("database", healthy=True)

        assert health.checks["api"] is True
        assert health.checks["database"] is True

    def test_mark_degraded(self):
        """Test marking component as degraded."""
        health = HealthCheck()

        health.register_check("cache", healthy=True)
        health.mark_degraded("cache", "High latency")

        assert health.checks["cache"] is False
        assert health.degraded_components["cache"] == "High latency"

    def test_healthy_status(self):
        """Test healthy status when all components healthy."""
        health = HealthCheck()

        health.register_check("api", healthy=True)
        health.register_check("database", healthy=True)

        assert health.get_status() == HealthStatus.HEALTHY

    def test_degraded_status(self):
        """Test degraded status when some components unhealthy."""
        health = HealthCheck()

        health.register_check("api", healthy=True)
        health.register_check("database", healthy=False)
        health.register_check("cache", healthy=True)

        assert health.get_status() == HealthStatus.DEGRADED

    def test_unhealthy_status(self):
        """Test unhealthy status when most components down."""
        health = HealthCheck()

        health.register_check("api", healthy=False)
        health.register_check("database", healthy=False)
        health.register_check("cache", healthy=True)

        assert health.get_status() == HealthStatus.UNHEALTHY

    def test_get_details(self):
        """Test getting detailed health information."""
        health = HealthCheck()

        health.register_check("api", healthy=True)
        health.register_check("database", healthy=True)
        health.mark_degraded("cache", "Slow")

        details = health.get_details()

        assert details["status"] == "degraded"
        assert details["checks"]["api"] is True
        assert details["checks"]["cache"] is False
        assert details["degraded"]["cache"] == "Slow"
        assert "timestamp" in details


class TestGlobalInstances:
    """Test global singleton instances."""

    def test_get_metrics_collector_singleton(self):
        """Test that get_metrics_collector returns same instance."""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2

    def test_get_alert_manager_singleton(self):
        """Test that get_alert_manager returns same instance."""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()

        assert manager1 is manager2

    def test_get_health_check_singleton(self):
        """Test that get_health_check returns same instance."""
        health1 = get_health_check()
        health2 = get_health_check()

        assert health1 is health2


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""

    def test_record_metric_convenience(self):
        """Test record_metric convenience function."""
        record_metric("test.metric", 42.0, "count")

        collector = get_metrics_collector()
        metrics = collector.get_metrics(name="test.metric")

        assert len(metrics) >= 1
        assert metrics[-1].value == 42.0

    def test_create_alert_convenience(self):
        """Test create_alert convenience function."""
        create_alert(
            AlertSeverity.INFO,
            "Test message",
            "test_component",
        )

        manager = get_alert_manager()
        alerts = manager.get_active_alerts(component="test_component")

        assert len(alerts) >= 1

    def test_register_health_check_convenience(self):
        """Test register_health_check convenience function."""
        register_health_check("test_component", healthy=True)

        health = get_health_check()

        assert health.checks["test_component"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
