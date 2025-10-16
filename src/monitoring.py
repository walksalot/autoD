"""
Monitoring and alerting infrastructure.

Provides:
- Structured metrics collection
- Health checks and readiness probes
- Performance monitoring
- Alert notifications
- Dashboard data export
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class Metric:
    """
    Individual metric data point.

    Attributes:
        name: Metric name (e.g., "api.response_time")
        value: Metric value
        unit: Unit of measurement (e.g., "ms", "count", "percent")
        timestamp: When metric was recorded
        labels: Additional metadata tags
    """

    name: str
    value: float
    unit: str
    timestamp: datetime
    labels: Dict[str, str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class Alert:
    """
    Alert notification.

    Attributes:
        severity: Alert severity level
        message: Alert message
        component: Component that triggered alert
        timestamp: When alert was created
        details: Additional context
    """

    severity: AlertSeverity
    message: str
    component: str
    timestamp: datetime
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


class MetricsCollector:
    """
    Central metrics collection and aggregation.

    Collects metrics from all components and provides aggregated views.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: List[Metric] = []
        self.max_metrics = 10000  # Prevent memory bloat
        self._start_time = datetime.now()

    def record(
        self,
        name: str,
        value: float,
        unit: str = "count",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a metric.

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            labels: Additional metadata tags
        """
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            labels=labels or {},
        )
        self.metrics.append(metric)

        # Trim old metrics if we exceed limit
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics :]

        # Log metric
        logger.debug(
            json.dumps(
                {
                    "event": "metric_recorded",
                    "metric": metric.to_dict(),
                }
            )
        )

    def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[Metric]:
        """
        Retrieve metrics matching criteria.

        Args:
            name: Filter by metric name
            since: Filter by timestamp (only metrics after this time)

        Returns:
            List of matching metrics
        """
        results = self.metrics

        if name:
            results = [m for m in results if m.name == name]

        if since:
            results = [m for m in results if m.timestamp >= since]

        return results

    def aggregate(
        self,
        name: str,
        window_minutes: int = 5,
    ) -> Dict[str, float]:
        """
        Aggregate metrics over a time window.

        Args:
            name: Metric name to aggregate
            window_minutes: Time window in minutes

        Returns:
            Dictionary with count, sum, avg, min, max
        """
        since = datetime.now() - timedelta(minutes=window_minutes)
        metrics = self.get_metrics(name=name, since=since)

        if not metrics:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
            }

        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def get_uptime_seconds(self) -> float:
        """Get system uptime in seconds."""
        return (datetime.now() - self._start_time).total_seconds()


class AlertManager:
    """
    Alert notification manager.

    Handles alert creation, deduplication, and notification.
    """

    def __init__(self, alert_file: Optional[Path] = None):
        """
        Initialize alert manager.

        Args:
            alert_file: File to persist alerts
        """
        self.alerts: List[Alert] = []
        self.alert_file = alert_file or Path("logs/alerts.jsonl")
        self.max_alerts = 1000
        self._last_alert_times: Dict[str, datetime] = {}

    def create_alert(
        self,
        severity: AlertSeverity,
        message: str,
        component: str,
        details: Optional[Dict[str, Any]] = None,
        dedupe_window_minutes: int = 5,
    ) -> None:
        """
        Create an alert.

        Args:
            severity: Alert severity
            message: Alert message
            component: Component that triggered alert
            details: Additional context
            dedupe_window_minutes: Suppress duplicate alerts within this window
        """
        # Deduplicate alerts
        alert_key = f"{component}:{message}"
        now = datetime.now()

        if alert_key in self._last_alert_times:
            last_time = self._last_alert_times[alert_key]
            if now - last_time < timedelta(minutes=dedupe_window_minutes):
                logger.debug(f"Suppressing duplicate alert: {alert_key}")
                return

        # Create alert
        alert = Alert(
            severity=severity,
            message=message,
            component=component,
            timestamp=now,
            details=details or {},
        )
        self.alerts.append(alert)
        self._last_alert_times[alert_key] = now

        # Trim old alerts
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts :]

        # Log alert
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }[severity]

        logger.log(
            log_level,
            json.dumps(
                {
                    "event": "alert_created",
                    "alert": alert.to_dict(),
                }
            ),
        )

        # Persist alert
        self._persist_alert(alert)

    def _persist_alert(self, alert: Alert) -> None:
        """Persist alert to disk."""
        try:
            self.alert_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.alert_file, "a") as f:
                f.write(json.dumps(alert.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist alert: {e}")

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        component: Optional[str] = None,
    ) -> List[Alert]:
        """
        Get active alerts.

        Args:
            severity: Filter by severity
            component: Filter by component

        Returns:
            List of active alerts
        """
        results = self.alerts

        if severity:
            results = [a for a in results if a.severity == severity]

        if component:
            results = [a for a in results if a.component == component]

        return results


class HealthCheck:
    """
    Health check system for monitoring component status.

    Provides readiness and liveness probes for orchestration systems.
    """

    def __init__(self):
        """Initialize health check system."""
        self.checks: Dict[str, bool] = {}
        self.degraded_components: Dict[str, str] = {}

    def register_check(self, component: str, healthy: bool) -> None:
        """
        Register health status for a component.

        Args:
            component: Component name
            healthy: Whether component is healthy
        """
        self.checks[component] = healthy

    def mark_degraded(self, component: str, reason: str) -> None:
        """
        Mark component as degraded.

        Args:
            component: Component name
            reason: Why component is degraded
        """
        self.degraded_components[component] = reason
        self.checks[component] = False

    def get_status(self) -> HealthStatus:
        """
        Get overall system health status.

        Returns:
            Overall health status
        """
        if not self.checks:
            return HealthStatus.HEALTHY

        unhealthy_count = sum(1 for v in self.checks.values() if not v)

        if unhealthy_count == 0:
            return HealthStatus.HEALTHY
        elif unhealthy_count < len(self.checks) / 2:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNHEALTHY

    def get_details(self) -> Dict[str, Any]:
        """
        Get detailed health information.

        Returns:
            Dictionary with health details
        """
        return {
            "status": self.get_status().value,
            "checks": self.checks,
            "degraded": self.degraded_components,
            "timestamp": datetime.now().isoformat(),
        }


# Global instances
_metrics_collector: Optional[MetricsCollector] = None
_alert_manager: Optional[AlertManager] = None
_health_check: Optional[HealthCheck] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def get_health_check() -> HealthCheck:
    """Get global health check instance."""
    global _health_check
    if _health_check is None:
        _health_check = HealthCheck()
    return _health_check


# Convenience functions


def record_metric(
    name: str,
    value: float,
    unit: str = "count",
    labels: Optional[Dict[str, str]] = None,
) -> None:
    """Record a metric."""
    get_metrics_collector().record(name, value, unit, labels)


def create_alert(
    severity: AlertSeverity,
    message: str,
    component: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Create an alert."""
    get_alert_manager().create_alert(severity, message, component, details)


def register_health_check(component: str, healthy: bool) -> None:
    """Register component health status."""
    get_health_check().register_check(component, healthy)
