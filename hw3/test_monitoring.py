from itertools import count

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from hw3.main import app
from shop_api.main import app as hw2_app
from store.cart import queries as cart_queries
from store.item import queries as item_queries


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(item_queries, "_items", {})
    monkeypatch.setattr(item_queries, "_id_generator", count(start=1))
    monkeypatch.setattr(cart_queries, "_carts", {})
    monkeypatch.setattr(cart_queries, "_id_generator", count(start=1))
    with TestClient(app) as client:
        yield client


def metric_samples(text, name):
    return {
        tuple(sorted(sample.labels.items())): sample.value
        for family in text_string_to_metric_families(text)
        for sample in family.samples
        if sample.name == name
    }


def test_uses_original_hw2_app(client):
    assert app is hw2_app
    assert app.title == "Shop API"
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/item", "/cart", "/cart/{cart_id}/add/{item_id}"} <= paths.keys()
    assert not any(path.startswith("/pokemon") for path in paths)


def test_monitored_item_cart_workflow(client):
    response = client.post("/item", json={"name": "Milk", "price": 12.5})
    assert response.status_code == 201
    item = response.json()
    response = client.post("/cart")
    assert response.status_code == 201
    cart = response.json()
    location = response.headers["location"]
    assert location == f"/cart/{cart['id']}"

    for quantity in [1, 2]:
        response = client.post(f"/cart/{cart['id']}/add/{item['id']}")
        assert response.status_code == 200
        assert response.json()["price"] == 12.5 * quantity
        assert response.json()["items"] == [
            {"id": item["id"], "name": "Milk", "quantity": quantity, "available": True}
        ]

    assert client.delete(f"/item/{item['id']}").status_code == 200
    assert client.get(f"/item/{item['id']}").status_code == 404
    assert client.get("/item").json() == []
    assert client.get(location).json()["items"][0]["available"] is False


def test_metrics_count_shop_requests_without_scrapes_or_raw_ids(client):
    before = client.get("/metrics")
    assert before.status_code == 200
    assert before.headers["content-type"].startswith("text/plain")
    counters_before = metric_samples(before.text, "http_requests_total")
    durations_before = metric_samples(before.text, "http_request_duration_seconds_count")

    assert client.get("/item").status_code == 200
    assert client.get("/item/12345").status_code == 404
    assert client.get("/item/67890").status_code == 404
    assert client.get("/cart").status_code == 200
    assert client.get("/cart/12345").status_code == 404
    assert client.get("/cart/67890").status_code == 404
    assert client.get("/item?limit=0").status_code == 422

    after = client.get("/metrics")
    counters_after = metric_samples(after.text, "http_requests_total")
    for handler, status, count in [
        ("/item", "2xx", 1),
        ("/item/{id}", "4xx", 2),
        ("/cart", "2xx", 1),
        ("/cart/{id}", "4xx", 2),
        ("/item", "4xx", 1),
    ]:
        labels = tuple(sorted(
            {"handler": handler, "method": "GET", "status": status}.items()
        ))
        assert counters_after[labels] - counters_before.get(labels, 0) == count

    durations_after = metric_samples(after.text, "http_request_duration_seconds_count")
    assert sum(durations_after.values()) - sum(durations_before.values()) == 7
    assert metric_samples(after.text, "http_request_duration_seconds_sum")
    assert metric_samples(after.text, "http_request_duration_highr_seconds_bucket")
    for labels in counters_after:
        handler = dict(labels)["handler"]
        assert handler != "/metrics"
        assert "12345" not in handler and "67890" not in handler
    assert metric_samples(client.get("/metrics").text, "http_requests_total") == counters_after
