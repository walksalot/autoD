"""
Unit tests for Prometheus metrics export.

Tests cover:
- Prometheus text format export
- JSON metrics export
- Cost calculation from token usage
- Histogram generation
- Metric aggregations
- Stage-specific metrics
- Error rate calculations
"""

import pytest
from datetime import datetime, timedelta

from src.metrics import PrometheusExporter
from src.monitoring import MetricsCollector, Metric


@pytest.fixture
def metrics_collector():
    """Create a fresh MetricsCollector for each test."""
    return MetricsCollector()


@pytest.fixture
def populated_collector(metrics_collector):
    """Create a MetricsCollector with sample data."""
    # Add processing duration metrics
    for duration in [500, 1200, 800, 1500, 2100]:
        metrics_collector.record(
            "processing.duration_ms",
            duration,
            "ms",
            {"doc_id": f"doc-{duration}"},
        )

    # Add token metrics
    for i in range(5):
        metrics_collector.record(
            "api.prompt_tokens",
            2000,
            "count",
            {"model": "gpt-5-mini"},
        )
        metrics_collector.record(
            "api.completion_tokens",
            500,
            "count",
            {"model": "gpt-5-mini"},
        )
        metrics_collector.record(
            "api.cached_tokens",
            1500,
            "count",
            {"model": "gpt-5-mini"},
        )

    # Add error metrics
    for stage in ["upload", "extraction", "vector_store"]:
        metrics_collector.record(
            "processing.error",
            1,
            "count",
            {"stage": stage},
        )

    # Add stage duration metrics
    metrics_collector.record(
        "stage.deduplication.duration_ms",
        50,
        "ms",
    )
    metrics_collector.record(
        "stage.upload.duration_ms",
        1200,
        "ms",
    )
    metrics_collector.record(
        "stage.extraction.duration_ms",
        8000,
        "ms",
    )

    # Add completion metric
    metrics_collector.record(
        "processing.complete",
        1,
        "count",
    )

    return metrics_collector


class TestPrometheusExporter:
    """Test Prometheus text format export."""

    def test_export_empty_collector(self, metrics_collector):
        """Test export with no metrics."""
        exporter = PrometheusExporter(metrics_collector)
        output = exporter.export_prometheus()

        assert "autod_up 1" in output
        assert "# HELP" in output
        assert "# TYPE" in output

    def test_export_includes_uptime(self, populated_collector):
        """Test that uptime metric is always included."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_uptime_seconds" in output
        assert "# HELP autod_uptime_seconds" in output
        assert "# TYPE autod_uptime_seconds gauge" in output

    def test_export_processing_histogram(self, populated_collector):
        """Test processing duration histogram export."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        # Check histogram structure
        assert "autod_processing_duration_ms_bucket" in output
        assert "autod_processing_duration_ms_sum" in output
        assert "autod_processing_duration_ms_count" in output

        # Check buckets
        assert 'le="1000"' in output
        assert 'le="2000"' in output
        assert 'le="+Inf"' in output

    def test_export_token_metrics(self, populated_collector):
        """Test token usage metrics export."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_prompt_tokens_total" in output
        assert "autod_completion_tokens_total" in output
        assert "autod_cached_tokens_total" in output

        # Check values (5 requests * token counts)
        assert "autod_prompt_tokens_total 10000" in output  # 5 * 2000
        assert "autod_completion_tokens_total 2500" in output  # 5 * 500
        assert "autod_cached_tokens_total 7500" in output  # 5 * 1500

    def test_export_cost_metric(self, populated_collector):
        """Test API cost calculation and export."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_api_cost_usd_total" in output

        # Calculate expected cost for gpt-5-mini:
        # Prompt: 10000 tokens * $1/1M = $0.01
        # Completion: 2500 tokens * $4/1M = $0.01
        # Cached: 7500 tokens * $0.20/1M = $0.0015
        # Total: $0.0215
        assert "autod_api_cost_usd_total 0.0215" in output

    def test_export_error_metrics(self, populated_collector):
        """Test error metrics by stage."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_errors_total" in output
        assert 'stage="upload"' in output
        assert 'stage="extraction"' in output
        assert 'stage="vector_store"' in output

    def test_export_stage_metrics(self, populated_collector):
        """Test stage-specific duration metrics."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_stage_deduplication_duration_ms" in output
        assert "autod_stage_upload_duration_ms" in output
        assert "autod_stage_extraction_duration_ms" in output

    def test_export_document_count(self, populated_collector):
        """Test total documents processed metric."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        assert "autod_documents_processed_total" in output
        assert "autod_documents_processed_total 1" in output

    def test_prometheus_format_structure(self, populated_collector):
        """Test Prometheus format compliance."""
        exporter = PrometheusExporter(populated_collector)
        output = exporter.export_prometheus()

        # Must end with newline
        assert output.endswith("\n")

        # Must have HELP and TYPE for each metric
        lines = output.split("\n")
        help_lines = [line for line in lines if line.startswith("# HELP")]
        type_lines = [line for line in lines if line.startswith("# TYPE")]

        assert len(help_lines) > 0
        assert len(type_lines) > 0

    def test_label_formatting(self, metrics_collector):
        """Test label formatting in Prometheus output."""
        metrics_collector.record(
            "test.metric",
            100,
            "count",
            {"label1": "value1", "label2": "value2"},
        )

        exporter = PrometheusExporter(metrics_collector)
        _ = exporter.export_prometheus()  # Output not used, testing label formatting

        # Labels should be sorted alphabetically
        # Format: metric{label1="value1",label2="value2"}
        # Note: This metric won't appear in standard export,
        # so we test _format_labels directly
        formatted = exporter._format_labels({"label1": "value1", "label2": "value2"})
        assert formatted == '{label1="value1",label2="value2"}'


class TestJSONExport:
    """Test JSON metrics export."""

    def test_json_export_structure(self, populated_collector):
        """Test JSON export has correct structure."""
        exporter = PrometheusExporter(populated_collector)
        result = exporter.export_json(window_minutes=60)

        assert "timestamp" in result
        assert "window_minutes" in result
        assert "uptime_seconds" in result
        assert "processing" in result
        assert "tokens" in result
        assert "errors" in result
        assert "stages" in result

    def test_json_processing_metrics(self, populated_collector):
        """Test processing metrics in JSON format."""
        exporter = PrometheusExporter(populated_collector)
        result = exporter.export_json(window_minutes=60)

        processing = result["processing"]
        assert processing["count"] == 5
        assert processing["min_ms"] == 500
        assert processing["max_ms"] == 2100
        assert processing["avg_ms"] == 1220  # (500+1200+800+1500+2100)/5

        # Check percentiles
        assert "p50_ms" in processing
        assert "p95_ms" in processing
        assert "p99_ms" in processing

    def test_json_token_metrics(self, populated_collector):
        """Test token metrics in JSON format."""
        exporter = PrometheusExporter(populated_collector)
        result = exporter.export_json(window_minutes=60)

        tokens = result["tokens"]
        assert tokens["prompt_tokens"] == 10000
        assert tokens["completion_tokens"] == 2500
        assert tokens["cached_tokens"] == 7500
        assert tokens["total_tokens"] == 12500

        # Cache hit rate: 7500 / (10000 + 7500) * 100 = 42.86%
        assert abs(tokens["cache_hit_rate_percent"] - 42.86) < 0.1

        # Cost
        assert abs(tokens["total_cost_usd"] - 0.0215) < 0.0001

    def test_json_error_metrics(self, populated_collector):
        """Test error metrics in JSON format."""
        exporter = PrometheusExporter(populated_collector)
        result = exporter.export_json(window_minutes=60)

        errors = result["errors"]
        assert errors["total_errors"] == 3
        assert errors["by_stage"]["upload"] == 1
        assert errors["by_stage"]["extraction"] == 1
        assert errors["by_stage"]["vector_store"] == 1

        # Error rate: 3 / (1 + 3) * 100 = 75%
        assert abs(errors["error_rate_percent"] - 75.0) < 0.1

    def test_json_stage_metrics(self, populated_collector):
        """Test stage-specific metrics in JSON format."""
        exporter = PrometheusExporter(populated_collector)
        result = exporter.export_json(window_minutes=60)

        stages = result["stages"]
        assert "deduplication" in stages
        assert "upload" in stages
        assert "extraction" in stages

        assert stages["deduplication"]["count"] == 1
        assert stages["deduplication"]["avg_ms"] == 50

    def test_json_empty_window(self, metrics_collector):
        """Test JSON export with window that has no metrics."""
        # Add metrics with old timestamps (outside the window)
        old_time = datetime.now() - timedelta(hours=2)
        old_metric = Metric(
            name="processing.duration_ms",
            value=1000,
            unit="ms",
            timestamp=old_time,
        )
        metrics_collector.metrics.append(old_metric)

        exporter = PrometheusExporter(metrics_collector)
        result = exporter.export_json(window_minutes=1)  # 1 minute window

        # Should have no processing metrics from the recent window
        assert result["processing"]["count"] == 0


class TestCostCalculation:
    """Test token cost calculation."""

    def test_cost_calculation_gpt5_mini(self, metrics_collector):
        """Test cost calculation for gpt-5-mini."""
        metrics_collector.record(
            "api.prompt_tokens", 1_000_000, "count", {"model": "gpt-5-mini"}
        )
        metrics_collector.record(
            "api.completion_tokens", 1_000_000, "count", {"model": "gpt-5-mini"}
        )
        metrics_collector.record(
            "api.cached_tokens", 1_000_000, "count", {"model": "gpt-5-mini"}
        )

        exporter = PrometheusExporter(metrics_collector)
        metrics_by_name = {
            "api.prompt_tokens": [
                m for m in metrics_collector.metrics if m.name == "api.prompt_tokens"
            ],
            "api.completion_tokens": [
                m
                for m in metrics_collector.metrics
                if m.name == "api.completion_tokens"
            ],
            "api.cached_tokens": [
                m for m in metrics_collector.metrics if m.name == "api.cached_tokens"
            ],
        }

        cost = exporter._calculate_total_cost(metrics_by_name)

        # Expected: $1 + $4 + $0.20 = $5.20
        assert abs(cost - 5.20) < 0.01

    def test_cost_calculation_gpt5(self, metrics_collector):
        """Test cost calculation for gpt-5."""
        metrics_collector.record(
            "api.prompt_tokens", 1_000_000, "count", {"model": "gpt-5"}
        )
        metrics_collector.record(
            "api.completion_tokens", 1_000_000, "count", {"model": "gpt-5"}
        )
        metrics_collector.record(
            "api.cached_tokens", 1_000_000, "count", {"model": "gpt-5"}
        )

        exporter = PrometheusExporter(metrics_collector)
        metrics_by_name = {
            "api.prompt_tokens": [
                m for m in metrics_collector.metrics if m.name == "api.prompt_tokens"
            ],
            "api.completion_tokens": [
                m
                for m in metrics_collector.metrics
                if m.name == "api.completion_tokens"
            ],
            "api.cached_tokens": [
                m for m in metrics_collector.metrics if m.name == "api.cached_tokens"
            ],
        }

        cost = exporter._calculate_total_cost(metrics_by_name)

        # Expected: $10 + $30 + $2 = $42.00
        assert abs(cost - 42.00) < 0.01

    def test_cost_calculation_mixed_models(self, metrics_collector):
        """Test cost calculation with mixed models."""
        metrics_collector.record(
            "api.prompt_tokens", 500_000, "count", {"model": "gpt-5"}
        )
        metrics_collector.record(
            "api.prompt_tokens", 500_000, "count", {"model": "gpt-5-mini"}
        )

        exporter = PrometheusExporter(metrics_collector)
        metrics_by_name = {
            "api.prompt_tokens": [
                m for m in metrics_collector.metrics if m.name == "api.prompt_tokens"
            ],
            "api.completion_tokens": [],
            "api.cached_tokens": [],
        }

        cost = exporter._calculate_total_cost(metrics_by_name)

        # Expected: (0.5M * $10/M) + (0.5M * $1/M) = $5 + $0.50 = $5.50
        assert abs(cost - 5.50) < 0.01


class TestHistogramGeneration:
    """Test histogram bucket generation."""

    def test_histogram_bucket_counts(self, metrics_collector):
        """Test histogram bucket distribution."""
        # Add values across different buckets
        values = [50, 250, 750, 1500, 2500, 6000, 15000]
        for val in values:
            metrics_collector.record("processing.duration_ms", val, "ms")

        exporter = PrometheusExporter(metrics_collector)
        output = exporter.export_prometheus()

        # Bucket 100: 1 value (50)
        # Bucket 500: 2 values (50, 250)
        # Bucket 1000: 3 values (50, 250, 750)
        # Bucket 2000: 4 values (50, 250, 750, 1500)
        # Bucket 5000: 5 values (50, 250, 750, 1500, 2500)
        # Bucket 10000: 6 values (50, 250, 750, 1500, 2500, 6000)
        # Bucket +Inf: 7 values (all)

        assert 'autod_processing_duration_ms_bucket{le="100"} 1' in output
        assert 'autod_processing_duration_ms_bucket{le="5000"} 5' in output
        assert 'autod_processing_duration_ms_bucket{le="+Inf"} 7' in output

    def test_histogram_sum_and_count(self, metrics_collector):
        """Test histogram sum and count."""
        values = [100, 200, 300]
        for val in values:
            metrics_collector.record("processing.duration_ms", val, "ms")

        exporter = PrometheusExporter(metrics_collector)
        output = exporter.export_prometheus()

        assert "autod_processing_duration_ms_sum 600" in output
        assert "autod_processing_duration_ms_count 3" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
