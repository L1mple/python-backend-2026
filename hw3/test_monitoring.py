from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from hw3.main import app


def counters(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    return {
        (sample.labels["method"], sample.labels["handler"], sample.labels["status"]): sample.value
        for metric in text_string_to_metric_families(response.text)
        for sample in metric.samples
        if sample.name == "shop_http_requests_total"
    }


def test_metrics_count_requests_and_exclude_health_and_scrapes():
    with TestClient(app) as client:
        before = counters(client)
        assert client.get("/health").json() == {"status": "ok"}
        assert counters(client) == before

        assert client.get("/item").status_code == 200
        assert client.get("/item/999999999999").status_code == 404
        after = counters(client)
        for key in [("GET", "/item", "200"), ("GET", "/item/{item_id}", "404")]:
            assert after[key] == before.get(key, 0) + 1

        metrics = client.get("/metrics").text
        assert "shop_http_request_duration_highr_seconds_bucket" in metrics
        assert 'handler="/health"' not in metrics
        assert 'handler="/metrics"' not in metrics


def test_monitoring_endpoints_are_not_in_shop_openapi():
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/metrics" not in paths
        assert "/health" not in paths
        assert "/item" in paths and "/cart" in paths
