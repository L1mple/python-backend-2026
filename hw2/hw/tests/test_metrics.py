from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from shop_api import main


def metric_value(client: TestClient, name: str, labels: dict[str, str]) -> float:
    for family in text_string_to_metric_families(client.get("/metrics").text):
        for sample in family.samples:
            if sample.name == name and sample.labels == labels:
                return sample.value
    return 0


def test_metrics_endpoint_is_excluded(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "http_request_duration_seconds" in response.text
    assert 'handler="/metrics"' not in client.get("/metrics").text
    assert "/metrics" not in client.get("/openapi.json").json()["paths"]


def test_item_ids_share_one_counter(client: TestClient) -> None:
    labels = {"handler": "/item/{item_id}", "method": "GET", "status": "200"}
    before = metric_value(client, "http_requests_total", labels)
    for name in ("First", "Second"):
        item = client.post("/item", json={"name": name, "price": 10}).json()
        assert client.get(f"/item/{item['id']}").status_code == 200
    assert metric_value(client, "http_requests_total", labels) == before + 2
    assert 'handler="/item/1"' not in client.get("/metrics").text


@pytest.mark.parametrize(
    ("path", "handler", "status"),
    [
        ("/item/0", "/item/{item_id}", 404),
        ("/item/not-an-int", "/item/{item_id}", 422),
        ("/missing", "none", 404),
    ],
)
def test_http_errors_are_counted(client: TestClient, path: str, handler: str, status: int) -> None:
    labels = {"handler": handler, "method": "GET", "status": str(status)}
    before = metric_value(client, "http_requests_total", labels)
    assert client.get(path).status_code == status
    assert metric_value(client, "http_requests_total", labels) == before + 1


def test_unhandled_error_is_counted(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    cart_id = client.post("/cart").json()["id"]
    monkeypatch.setattr(main.store, "get_cart", Mock(side_effect=RuntimeError("Test failure")))
    labels = {"handler": "/cart/{cart_id}", "method": "GET", "status": "500"}
    before = metric_value(client, "http_requests_total", labels)
    with TestClient(main.app, raise_server_exceptions=False) as error_client:
        assert error_client.get(f"/cart/{cart_id}").status_code == 500
    assert metric_value(client, "http_requests_total", labels) == before + 1
