from types import SimpleNamespace

from app.monitoring.metrics import Metrics
from app.monitoring.usage import RequestUsage, current_usage, record_usage


def test_usage_and_cost():
    metrics = Metrics()
    usage = RequestUsage(metrics, {"demo": (2.0, 4.0)})
    token = current_usage.set(usage)
    try:
        response = SimpleNamespace(usage_metadata=SimpleNamespace(
            prompt_token_count=10, candidates_token_count=4, thoughts_token_count=1,
        ))
        record_usage("gemini", "demo", response)
        record_usage("gemini", "unpriced", response)
    finally:
        current_usage.reset(token)
    assert usage.input_tokens == 20
    assert usage.output_tokens == 10
    assert usage.estimated_cost_usd == 0.00004
    assert usage.unpriced_calls == 1
    assert metrics.snapshot()["counts"]["llm.gemini.calls"] == 2


def test_metrics_key_and_percentiles(client):
    from pydantic import SecretStr

    metrics = client.app.state.metrics
    for seconds in (0.001, 0.002, 0.003, 0.004):
        metrics.observe("demo", seconds)
    assert client.get("/metrics").status_code == 404
    client.app.state.settings.metrics_key = SecretStr("test-local-metrics")
    report = client.get("/metrics", headers={"X-Metrics-Key": "test-local-metrics"}).json()
    assert report["latency_ms"]["demo"] == {"p50": 2.0, "p95": 4.0, "p99": 4.0, "samples": 4}
