import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from shop_api.main import app


@pytest.mark.parametrize("duration,interval", [(0, 0.1), (3601, 0.1), (1, 0), (1, 61)])
def test_load_rejects_unbounded_parameters(duration, interval):
    spec = importlib.util.spec_from_file_location(
        "load_shop", Path(__file__).resolve().parents[2] / "scripts/load_shop.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError):
        module.ShopLoad(None).run(duration, interval)


def test_metrics_record_api_requests_and_normalize_paths():
    with TestClient(app) as client:
        client.get("/item/0")
        client.get("/item/999999")
        response = client.get("/metrics")
    assert response.status_code == 200
    samples = [
        sample
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    ]
    assert any(sample.name == "python_info" and sample.value == 1 for sample in samples)
    requests = [sample for sample in samples if sample.name == "http_requests_total"]
    assert any(
        sample.labels.get("handler") == "/item/{item_id}"
        and sample.labels.get("status") == "4xx"
        and sample.value >= 2
        for sample in requests
    )
    assert not any(sample.labels.get("handler") == "/metrics" for sample in requests)


def test_load_exercises_real_cart_operations(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "load_shop", Path(__file__).resolve().parents[2] / "scripts/load_shop.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock = iter((0, 0, 2))
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None),
    )
    with TestClient(app) as client:
        assert module.ShopLoad(client).run(1, 0.1) == 1
        carts = client.get("/cart", params={"limit": 10000}).json()
        cart = carts[-1]
        assert cart["items"][0]["quantity"] == 1
        assert cart["price"] == 10


def metric_values(client):
    return {
        (sample.name, tuple(sorted(sample.labels.items()))): sample.value
        for family in text_string_to_metric_families(client.get("/metrics").text)
        for sample in family.samples
    }


def test_product_metrics_track_outcomes_and_observed_carts():
    with TestClient(app) as client:
        before = metric_values(client)
        item = client.post("/item", json={"name": "Metrics item", "price": 7}).json()
        cart_id = client.post("/cart").json()["id"]
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 200
        client.delete(f"/item/{item['id']}")
        assert client.get(f"/cart/{cart_id}").json()["price"] == 0
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 404
        client.get("/item", params={"min_price": 1})
        after = metric_values(client)

    def delta(name, **labels):
        key = (name, tuple(sorted(labels.items())))
        return after.get(key, 0) - before.get(key, 0)

    assert delta("shop_created_total", resource="item") == 1
    assert delta("shop_created_total", resource="cart") == 1
    assert delta("shop_item_deletions_total") == 1
    assert delta("shop_cart_additions_total", result="success") == 1
    assert delta("shop_cart_additions_total", result="not_found") == 1
    assert delta("shop_cart_value_sum") == 7
    assert delta("shop_cart_quantity_sum") == 2
    assert delta("shop_cart_unavailable_quantity_sum") == 1
    assert (
        delta(
            "shop_stage_duration_seconds_count",
            stage="cart_mutation",
            result="not_found",
        )
        == 1
    )
    assert (
        delta(
            "shop_stage_duration_seconds_count",
            stage="catalog_filter",
            result="success",
        )
        == 1
    )
    for (name, labels), value in after.items():
        if name.startswith("shop_"):
            assert set(dict(labels)) <= {"resource", "stage", "result", "le"}
            assert not any(str(item["id"]) == v for k, v in labels if k != "le")


def test_rejected_cart_addition_has_separate_metric_and_timed_stage():
    with TestClient(app) as client:
        item = client.post("/item", json={"name": "Large", "price": 1e308}).json()
        cart_id = client.post("/cart").json()["id"]
        client.post(f"/cart/{cart_id}/add/{item['id']}")
        before = metric_values(client)
        assert client.post(f"/cart/{cart_id}/add/{item['id']}").status_code == 422
        after = metric_values(client)
    for name, labels in (
        ("shop_cart_additions_total", {"result": "rejected"}),
        (
            "shop_stage_duration_seconds_count",
            {"stage": "cart_mutation", "result": "rejected"},
        ),
    ):
        key = (name, tuple(sorted(labels.items())))
        assert after.get(key, 0) - before.get(key, 0) == 1


def test_load_observes_unavailable_items_and_failed_additions(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "load_shop", Path(__file__).resolve().parents[2] / "scripts/load_shop.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock = iter((0, 0, 2))
    monkeypatch.setattr(
        module,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None),
    )
    with TestClient(app) as client:
        before = metric_values(client)
        assert module.ShopLoad(client).run(1, 0.1) == 1
        after = metric_values(client)
    key = ("shop_cart_additions_total", (("result", "not_found"),))
    assert after.get(key, 0) - before.get(key, 0) == 1
    key = ("shop_cart_unavailable_quantity_sum", ())
    assert after.get(key, 0) - before.get(key, 0) == 1
