from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from hw3.main import app


def test_http_metrics() -> None:
    """Метрики различают статусы, но объединяют ID в шаблон маршрута."""
    labels = {"handler": "/item/{item_id}", "method": "GET", "status": "404"}
    before = REGISTRY.get_sample_value("http_requests_total", labels) or 0
    with TestClient(app) as client:
        assert client.get("/item/0").status_code == 404
        assert client.get("/item/-1").status_code == 404
        assert client.get("/item?limit=0").status_code == 422
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert REGISTRY.get_sample_value("http_requests_total", labels) == before + 2
    assert (
        REGISTRY.get_sample_value(
            "http_requests_total",
            {"handler": "/item", "method": "GET", "status": "422"},
        )
        >= 1
    )
    assert (
        'http_request_duration_seconds_bucket{handler="/item/{item_id}"'
        in response.text
    )


def test_scrapes_are_excluded() -> None:
    with TestClient(app) as client:
        client.get("/metrics")
        response = client.get("/metrics")
    assert 'handler="/metrics"' not in response.text


def test_websocket_still_works() -> None:
    with (
        TestClient(app) as client,
        client.websocket_connect("/chat/hw3-test") as sender,
        client.websocket_connect("/chat/hw3-test") as receiver,
    ):
        sender.send_text("hello")
        assert receiver.receive_text().endswith(" :: hello")
