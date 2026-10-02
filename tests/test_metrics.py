"""Hermetic tests for Prometheus infrastructure metrics."""

from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge

import src.core.metrics as metrics_mod
from src.config.settings import settings
from src.core.metrics import (
    DB_POOL_CHECKED_IN,
    DB_POOL_CHECKED_OUT,
    DB_POOL_SIZE,
    DB_UP,
    PROCESS_UPTIME_SECONDS,
    QUEUE_DEPTH,
    REDIS_UP,
    REGISTRY,
    metrics_response,
    update_infra_gauges,
)


def test_metrics_module_import_and_gauges_exist():
    """Import test: gauges and collector registry exist without connecting to live services."""
    assert isinstance(REGISTRY, CollectorRegistry)
    assert isinstance(QUEUE_DEPTH, Gauge)
    assert isinstance(DB_POOL_SIZE, Gauge)
    assert isinstance(DB_POOL_CHECKED_OUT, Gauge)
    assert isinstance(DB_POOL_CHECKED_IN, Gauge)
    assert isinstance(PROCESS_UPTIME_SECONDS, Gauge)
    assert isinstance(REDIS_UP, Gauge)
    assert isinstance(DB_UP, Gauge)


@pytest.mark.anyio
async def test_metrics_endpoint_content(client):
    """Content test: verify /metrics route returns Prometheus text with expected gauges."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(CONTENT_TYPE_LATEST)

    text = response.text
    assert 'queue_depth{process="backend"}' in text
    assert 'db_pool_size{process="backend"}' in text
    assert 'db_pool_checked_out{process="backend"}' in text
    assert 'process_uptime_seconds{process="backend"}' in text
    assert 'redis_up{process="backend"}' in text
    assert 'db_up{process="backend"}' in text


def test_metrics_response_direct_update():
    """Verify metrics_response() after direct update_infra_gauges() call."""
    update_infra_gauges(process="worker")
    text = metrics_response()
    assert 'queue_depth{process="worker"}' in text
    assert 'db_pool_size{process="worker"}' in text
    assert 'db_pool_checked_out{process="worker"}' in text
    assert 'process_uptime_seconds{process="worker"}' in text


def test_metrics_degraded_behaviour_on_reader_exceptions(monkeypatch):
    """Degraded-behaviour test: monkeypatch readers to raise; metrics_response still succeeds."""

    def raise_err(*_args, **_kwargs):
        msg = "Simulated connection failure"
        raise ConnectionError(msg)

    monkeypatch.setattr(metrics_mod, "_read_queue_depth", raise_err)
    monkeypatch.setattr(metrics_mod, "_read_db_pool", raise_err)

    # Calling update_infra_gauges must not raise an exception
    update_infra_gauges(process="backend")
    text = metrics_response()

    # AC-4: Responds with uptime gauge and zeroed/stale degraded gauges without exception
    assert 'process_uptime_seconds{process="backend"}' in text
    assert 'redis_up{process="backend"} 0.0' in text
    assert 'db_up{process="backend"} 0.0' in text


def test_metrics_cardinality_labelnames_subset_of_process():
    """Cardinality test: gauges and collector labels must only contain 'process'."""
    allowed_labels = {"process"}

    # Inspect all registered collectors
    for collector in REGISTRY._collector_to_names:
        labelnames = set(getattr(collector, "_labelnames", ()))
        assert labelnames.issubset(allowed_labels), (
            f"Collector {collector} has forbidden labels: {labelnames - allowed_labels}"
        )

    # Inspect all collected metric samples
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            sample_labels = set(sample.labels.keys())
            assert sample_labels.issubset(allowed_labels), (
                f"Sample {sample.name} has forbidden labels: {sample_labels - allowed_labels}"
            )


def test_worker_gating_in_test_environment(monkeypatch):
    """Gating test: with ENVIRONMENT=test, setup_worker_services never starts an HTTP server."""
    from src.worker import setup_worker_services

    with patch("prometheus_client.start_http_server") as mock_start_http:
        setup_worker_services()
        mock_start_http.assert_not_called()


def test_worker_starts_server_when_enabled_outside_test(monkeypatch):
    """Verify worker starts server and updater when environment != 'test'."""
    from src.worker import setup_worker_services

    monkeypatch.setattr(settings, "environment", "dev")
    monkeypatch.setattr(settings, "enable_metrics", True)
    monkeypatch.setattr(settings, "worker_metrics_port", 8004)

    with (
        patch("prometheus_client.start_http_server") as mock_start_http,
        patch("src.core.metrics.start_worker_metrics_updater") as mock_updater,
    ):
        setup_worker_services()
        mock_start_http.assert_called_once_with(
            port=8004,
            addr="0.0.0.0",
            registry=REGISTRY,
        )
        mock_updater.assert_called_once()
