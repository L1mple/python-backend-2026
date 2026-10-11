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
    assert any(
        sample.name == "python_info" and sample.value == 1 for sample in samples
    )
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
        module, "time",
        SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None),
    )
    with TestClient(app) as client:
        assert module.ShopLoad(client).run(1, 0.1) == 1
        carts = client.get("/cart", params={"limit": 10000}).json()
        cart = carts[-1]
        assert cart["items"][0]["quantity"] == 1
        assert cart["price"] == 10
