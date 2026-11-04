"""Тесты ресурса /item: ошибки, валидация, фильтры и пагинация."""

import pytest
from fastapi.testclient import TestClient

MISSING_ID = 2_000_000_000  # заведомо несуществующий id


def test_post_item_returns_location_and_stores_item(client: TestClient) -> None:
    response = client.post("/item", json={"name": "Хлеб", "price": 45.5})

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/item/{body['id']}"
    assert body == {"id": body["id"], "name": "Хлеб", "price": 45.5, "deleted": False}
    assert client.get(f"/item/{body['id']}").json() == body


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "price": 1.0},  # пустое название
        {"name": "x", "price": -1.0},  # отрицательная цена
        {"name": "x"},  # нет цены
        {"name": "x", "price": 1.0, "deleted": True},  # лишнее поле
    ],
)
def test_post_item_validation(client: TestClient, body: dict) -> None:
    assert client.post("/item", json=body).status_code == 422


def test_get_missing_item_is_404(client: TestClient) -> None:
    assert client.get(f"/item/{MISSING_ID}").status_code == 404


def test_get_deleted_item_is_404(client: TestClient, make_item) -> None:
    item = make_item()
    client.delete(f"/item/{item['id']}")

    assert client.get(f"/item/{item['id']}").status_code == 404


def test_put_replaces_item(client: TestClient, make_item) -> None:
    item = make_item(name="Старое", price=1.0)

    response = client.put(f"/item/{item['id']}", json={"name": "Новое", "price": 2.5})

    assert response.status_code == 200
    assert response.json() == {"id": item["id"], "name": "Новое", "price": 2.5, "deleted": False}
    assert client.get(f"/item/{item['id']}").json()["name"] == "Новое"


def test_put_missing_item_is_404(client: TestClient) -> None:
    assert client.put(f"/item/{MISSING_ID}", json={"name": "x", "price": 1.0}).status_code == 404


def test_put_deleted_item_is_not_modified(client: TestClient, make_item) -> None:
    item = make_item()
    client.delete(f"/item/{item['id']}")

    response = client.put(f"/item/{item['id']}", json={"name": "Воскрес", "price": 1.0})

    assert response.status_code == 304
    assert client.get(f"/item/{item['id']}").status_code == 404  # осталась удаленной


def test_patch_changes_only_given_fields(client: TestClient, make_item) -> None:
    item = make_item(name="Сыр", price=100.0)

    response = client.patch(f"/item/{item['id']}", json={"price": 120.0})

    assert response.status_code == 200
    assert response.json() == {"id": item["id"], "name": "Сыр", "price": 120.0, "deleted": False}


def test_patch_name_only(client: TestClient, make_item) -> None:
    item = make_item(name="Сыр", price=100.0)

    response = client.patch(f"/item/{item['id']}", json={"name": "Сыр \"Гауда\""})

    assert response.json()["name"] == "Сыр \"Гауда\""
    assert response.json()["price"] == 100.0


def test_patch_missing_item_is_404(client: TestClient) -> None:
    assert client.patch(f"/item/{MISSING_ID}", json={"price": 1.0}).status_code == 404


@pytest.mark.parametrize("body", [{"name": None}, {"price": None}, {"name": ""}, {"price": -5}])
def test_patch_rejects_invalid_values(client: TestClient, make_item, body: dict) -> None:
    item = make_item()

    assert client.patch(f"/item/{item['id']}", json=body).status_code == 422


def test_delete_marks_item_deleted_and_is_idempotent(client: TestClient, make_item) -> None:
    item = make_item()

    assert client.delete(f"/item/{item['id']}").status_code == 200
    assert client.delete(f"/item/{item['id']}").status_code == 200

    deleted = [i for i in client.get("/item", params={"show_deleted": True, "limit": 10_000}).json() if i["id"] == item["id"]]
    assert deleted and deleted[0]["deleted"] is True


def test_delete_missing_item_is_404(client: TestClient) -> None:
    assert client.delete(f"/item/{MISSING_ID}").status_code == 404


def test_item_list_hides_deleted_unless_asked(client: TestClient, make_item) -> None:
    alive, dead = make_item(), make_item()
    client.delete(f"/item/{dead['id']}")

    default_ids = {i["id"] for i in client.get("/item", params={"limit": 10_000}).json()}
    with_deleted_ids = {i["id"] for i in client.get("/item", params={"limit": 10_000, "show_deleted": True}).json()}

    assert alive["id"] in default_ids and dead["id"] not in default_ids
    assert {alive["id"], dead["id"]} <= with_deleted_ids


def test_item_list_price_filters(client: TestClient, make_item) -> None:
    cheap, middle, pricey = make_item(price=1_000_001.0), make_item(price=1_000_002.0), make_item(price=1_000_003.0)

    in_range = client.get("/item", params={"min_price": 1_000_002.0, "max_price": 1_000_002.0, "limit": 100}).json()
    at_least = {i["id"] for i in client.get("/item", params={"min_price": 1_000_002.0, "limit": 1000}).json()}
    at_most = {i["id"] for i in client.get("/item", params={"max_price": 1_000_002.0, "limit": 100_000}).json()}

    assert middle["id"] in {i["id"] for i in in_range}
    assert cheap["id"] not in {i["id"] for i in in_range} and pricey["id"] not in {i["id"] for i in in_range}
    assert {middle["id"], pricey["id"]} <= at_least and cheap["id"] not in at_least
    assert {cheap["id"], middle["id"]} <= at_most and pricey["id"] not in at_most


def test_item_list_pagination_is_consistent(client: TestClient, make_item) -> None:
    for _ in range(5):
        make_item()
    full = client.get("/item", params={"limit": 10_000}).json()

    page = client.get("/item", params={"offset": 2, "limit": 3}).json()

    assert len(page) == 3
    assert page == full[2:5]
    assert client.get("/item", params={"offset": len(full) + 10}).json() == []
