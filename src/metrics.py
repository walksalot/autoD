"""
Prometheus-compatible metrics export for monitoring and alerting.

Provides:
- Prometheus text format export (/metrics)
- JSON format export (/metrics/json)
- Cost tracking (token usage and pricing)
- Processing time distributions
- Error rate tracking by stage
- System health metrics
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.monitoring import get_metrics_collector, Metric


logger = logging.getLogger("paper_autopilot")


class PrometheusExporter:
    """
    Export metrics in Prometheus text format.

    Prometheus expects metrics in this format:
    # HELP metric_name description
    # TYPE metric_name type
    metric_name{label1="value1",label2="value2"} value timestamp
    """

    # Metric type mappings
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

    # OpenAI pricing (per 1M tokens) - GPT-5 rates
    PRICING = {
        "gpt-5": {
            "prompt": 10.00,  # $10/1M tokens
            "completion": 30.00,  # $30/1M tokens
            "cached_prompt": 2.00,  # $2/1M tokens (80% discount)
        },
        "gpt-5-mini": {
            "prompt": 1.00,  # $1/1M tokens
            "completion": 4.00,  # $4/1M tokens
            "cached_prompt": 0.20,  # $0.20/1M tokens (80% discount)
        },
    }

    def __init__(self, metrics_collector: Optional[Any] = None) -> None:
        """
        Initialize Prometheus exporter.

        Args:
            metrics_collector: Optional MetricsCollector instance
        """
        self.collector = metrics_collector or get_metrics_collector()

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """
        Format labels for Prometheus format.

        Args:
            labels: Dictionary of label key-value pairs

        Returns:
            Formatted label string: {key1="value1",key2="value2"}
        """
        if not labels:
            return ""

        items = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"

    def _format_metric_line(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Format a single metric line in Prometheus format.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
            timestamp: Optional timestamp (milliseconds since epoch)

        Returns:
            Formatted metric line
        """
        label_str = self._format_labels(labels or {})
        timestamp_ms = int(timestamp.timestamp() * 1000) if timestamp else ""

        if timestamp_ms:
            return f"{name}{label_str} {value} {timestamp_ms}"
        else:
            return f"{name}{label_str} {value}"

    def _add_metric_header(
        self, lines: List[str], name: str, help_text: str, metric_type: str
    ) -> None:
        """Add metric header (HELP and TYPE)."""
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")

    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus text format.

        Returns:
            Prometheus-formatted text
        """
        lines: List[str] = []

        # Get all metrics from collector
        all_metrics = self.collector.metrics

        if not all_metrics:
            # Return minimal metrics even if no data
            self._add_metric_header(
                lines, "autod_up", "AutoD service is up", self.GAUGE
            )
            lines.append("autod_up 1")
            return "\n".join(lines) + "\n"

        # Group metrics by name
        metrics_by_name: Dict[str, List[Metric]] = defaultdict(list)
        for metric in all_metrics:
            metrics_by_name[metric.name].append(metric)

        # Export uptime
        self._add_metric_header(
            lines,
            "autod_uptime_seconds",
            "Time since service started",
            self.GAUGE,
        )
        lines.append(
            self._format_metric_line(
                "autod_uptime_seconds", self.collector.get_uptime_seconds()
            )
        )

        # Export processing time metrics
        if "processing.duration_ms" in metrics_by_name:
            self._export_processing_time(
                lines, metrics_by_name["processing.duration_ms"]
            )

        # Export token usage and cost
        if "api.prompt_tokens" in metrics_by_name:
            self._export_token_metrics(lines, metrics_by_name)

        # Export error rates
        if "processing.error" in metrics_by_name:
            self._export_error_metrics(lines, metrics_by_name["processing.error"])

        # Export stage-specific metrics
        self._export_stage_metrics(lines, metrics_by_name)

        # Export request counts
        if "processing.complete" in metrics_by_name:
            self._add_metric_header(
                lines,
                "autod_documents_processed_total",
                "Total documents processed",
                self.COUNTER,
            )
            lines.append(
                self._format_metric_line(
                    "autod_documents_processed_total",
                    len(metrics_by_name["processing.complete"]),
                )
            )

        return "\n".join(lines) + "\n"

    def _export_processing_time(self, lines: List[str], metrics: List[Metric]) -> None:
        """Export processing time distribution as histogram."""
        self._add_metric_header(
            lines,
            "autod_processing_duration_ms",
            "Document processing duration in milliseconds",
            self.HISTOGRAM,
        )

        # Calculate histogram buckets
        values = [m.value for m in metrics]
        buckets = [100, 500, 1000, 2000, 5000, 10000, 30000, float("inf")]

        # Count values in each bucket (cumulative)
        # For each bucket, count how many values are <= that threshold
        for bucket in buckets:
            count = sum(1 for v in values if v <= bucket)
            le_label = "+Inf" if bucket == float("inf") else str(bucket)
            lines.append(
                self._format_metric_line(
                    "autod_processing_duration_ms_bucket",
                    count,
                    {"le": le_label},
                )
            )

        # Export sum and count
        lines.append(
            self._format_metric_line("autod_processing_duration_ms_sum", sum(values))
        )
        lines.append(
            self._format_metric_line("autod_processing_duration_ms_count", len(values))
        )

    def _export_token_metrics(
        self, lines: List[str], metrics_by_name: Dict[str, List[Metric]]
    ) -> None:
        """Export token usage and cost metrics."""
        # Token counts
        for token_type in ["prompt_tokens", "completion_tokens", "cached_tokens"]:
            metric_name = f"api.{token_type}"
            if metric_name in metrics_by_name:
                total_tokens = sum(m.value for m in metrics_by_name[metric_name])

                self._add_metric_header(
                    lines,
                    f"autod_{token_type}_total",
                    f"Total {token_type.replace('_', ' ')} used",
                    self.COUNTER,
                )
                lines.append(
                    self._format_metric_line(f"autod_{token_type}_total", total_tokens)
                )

        # Calculate cost
        total_cost = self._calculate_total_cost(metrics_by_name)
        if total_cost > 0:
            self._add_metric_header(
                lines,
                "autod_api_cost_usd_total",
                "Total API cost in USD",
                self.COUNTER,
            )
            lines.append(
                self._format_metric_line("autod_api_cost_usd_total", total_cost)
            )

    def _calculate_total_cost(self, metrics_by_name: Dict[str, List[Metric]]) -> float:
        """
        Calculate total API cost from token usage.

        Returns:
            Total cost in USD
        """
        cost = 0.0

        # Get token metrics
        prompt_tokens = metrics_by_name.get("api.prompt_tokens", [])
        completion_tokens = metrics_by_name.get("api.completion_tokens", [])
        cached_tokens = metrics_by_name.get("api.cached_tokens", [])

        # Sum tokens by model
        for metrics_list, token_type in [
            (prompt_tokens, "prompt"),
            (completion_tokens, "completion"),
            (cached_tokens, "cached_prompt"),
        ]:
            for metric in metrics_list:
                model = metric.labels.get("model", "gpt-5-mini")

                # Get pricing for model
                pricing = self.PRICING.get(model, self.PRICING["gpt-5-mini"])
                price_per_million = pricing.get(token_type, 0.0)

                # Calculate cost
                cost += (metric.value / 1_000_000) * price_per_million

        return round(cost, 6)

    def _export_error_metrics(
        self, lines: List[str], error_metrics: List[Metric]
    ) -> None:
        """Export error rate metrics by stage."""
        self._add_metric_header(
            lines,
            "autod_errors_total",
            "Total errors by stage",
            self.COUNTER,
        )

        # Group by stage
        errors_by_stage: Dict[str, int] = defaultdict(int)
        for metric in error_metrics:
            stage = metric.labels.get("stage", "unknown")
            errors_by_stage[stage] += 1

        # Export counts by stage
        for stage, count in errors_by_stage.items():
            lines.append(
                self._format_metric_line("autod_errors_total", count, {"stage": stage})
            )

    def _export_stage_metrics(
        self, lines: List[str], metrics_by_name: Dict[str, List[Metric]]
    ) -> None:
        """Export stage-specific metrics."""
        # Common stages
        stages = [
            "deduplication",
            "upload",
            "extraction",
            "vector_store",
        ]

        for stage in stages:
            stage_duration_name = f"stage.{stage}.duration_ms"
            if stage_duration_name in metrics_by_name:
                metrics = metrics_by_name[stage_duration_name]
                values = [m.value for m in metrics]

                self._add_metric_header(
                    lines,
                    f"autod_stage_{stage}_duration_ms",
                    f"{stage.capitalize()} stage duration in milliseconds",
                    self.SUMMARY,
                )
                lines.append(
                    self._format_metric_line(
                        f"autod_stage_{stage}_duration_ms_sum", sum(values)
                    )
                )
                lines.append(
                    self._format_metric_line(
                        f"autod_stage_{stage}_duration_ms_count", len(values)
                    )
                )

    def export_json(self, window_minutes: int = 60) -> Dict[str, Any]:
        """
        Export metrics in JSON format for custom dashboards.

        Args:
            window_minutes: Time window for aggregations (default: 1 hour)

        Returns:
            Dictionary with metrics summary
        """
        since = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = self.collector.get_metrics(since=since)

        # Group by name
        metrics_by_name: Dict[str, List[Metric]] = defaultdict(list)
        for metric in recent_metrics:
            metrics_by_name[metric.name].append(metric)

        # Build JSON response
        return {
            "timestamp": datetime.now().isoformat() + "Z",
            "window_minutes": window_minutes,
            "uptime_seconds": self.collector.get_uptime_seconds(),
            "processing": self._json_processing_metrics(metrics_by_name),
            "tokens": self._json_token_metrics(metrics_by_name),
            "errors": self._json_error_metrics(metrics_by_name),
            "stages": self._json_stage_metrics(metrics_by_name),
        }

    def _json_processing_metrics(
        self, metrics_by_name: Dict[str, List[Metric]]
    ) -> Dict[str, Any]:
        """Get processing metrics for JSON export."""
        duration_metrics = metrics_by_name.get("processing.duration_ms", [])

        if not duration_metrics:
            return {"count": 0}

        values = [m.value for m in duration_metrics]
        values.sort()

        return {
            "count": len(values),
            "avg_ms": sum(values) / len(values),
            "min_ms": min(values),
            "max_ms": max(values),
            "p50_ms": values[len(values) // 2],
            "p95_ms": values[int(len(values) * 0.95)],
            "p99_ms": values[int(len(values) * 0.99)],
        }

    def _json_token_metrics(
        self, metrics_by_name: Dict[str, List[Metric]]
    ) -> Dict[str, Any]:
        """Get token usage metrics for JSON export."""
        prompt_tokens = sum(
            m.value for m in metrics_by_name.get("api.prompt_tokens", [])
        )
        completion_tokens = sum(
            m.value for m in metrics_by_name.get("api.completion_tokens", [])
        )
        cached_tokens = sum(
            m.value for m in metrics_by_name.get("api.cached_tokens", [])
        )

        total_cost = self._calculate_total_cost(metrics_by_name)

        # Calculate cache hit rate
        total_prompt_tokens = prompt_tokens + cached_tokens
        cache_hit_rate = (
            (cached_tokens / total_prompt_tokens * 100)
            if total_prompt_tokens > 0
            else 0.0
        )

        return {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "cached_tokens": int(cached_tokens),
            "total_tokens": int(prompt_tokens + completion_tokens),
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "total_cost_usd": round(total_cost, 6),
        }

    def _json_error_metrics(
        self, metrics_by_name: Dict[str, List[Metric]]
    ) -> Dict[str, Any]:
        """Get error metrics for JSON export."""
        error_metrics = metrics_by_name.get("processing.error", [])
        complete_metrics = metrics_by_name.get("processing.complete", [])

        total_requests = len(complete_metrics) + len(error_metrics)
        error_rate = (
            (len(error_metrics) / total_requests * 100) if total_requests > 0 else 0.0
        )

        # Group by stage
        errors_by_stage: Dict[str, int] = defaultdict(int)
        for metric in error_metrics:
            stage = metric.labels.get("stage", "unknown")
            errors_by_stage[stage] += 1

        return {
            "total_errors": len(error_metrics),
            "error_rate_percent": round(error_rate, 2),
            "by_stage": dict(errors_by_stage),
        }

    def _json_stage_metrics(
        self, metrics_by_name: Dict[str, List[Metric]]
    ) -> Dict[str, Any]:
        """Get stage-specific metrics for JSON export."""
        stages = {}

        for stage in ["deduplication", "upload", "extraction", "vector_store"]:
            stage_duration_name = f"stage.{stage}.duration_ms"
            if stage_duration_name in metrics_by_name:
                values = [m.value for m in metrics_by_name[stage_duration_name]]
                values.sort()

                stages[stage] = {
                    "count": len(values),
                    "avg_ms": sum(values) / len(values),
                    "p95_ms": values[int(len(values) * 0.95)] if values else 0,
                }

        return stages
