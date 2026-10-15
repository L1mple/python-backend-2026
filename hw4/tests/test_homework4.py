import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

TEST_DATABASE = Path(__file__).with_name("test_shop.db").resolve()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DATABASE}")

from shop_api.database import Base, engine
from shop_api.main import app

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    TEST_DATABASE.unlink(missing_ok=True)


def create_item(price: float = 99.99) -> dict:
    response = client.post(
        "/item",
        json={"name": f"Товар {uuid4().hex}", "price": price},
    )
    assert response.status_code == HTTPStatus.CREATED
    return response.json()


def create_cart() -> int:
    response = client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    return response.json()["id"]


def test_health_checks_database_connection() -> None:
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_create_and_get_item() -> None:
    item = create_item(125.50)
    response = client.get(f"/item/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == item
    assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "Без цены"},
        {"name": "Отрицательная цена", "price": -1},
        {"name": "Лишнее поле", "price": 10, "unknown": True},
    ],
)
def test_create_item_validation(body: dict) -> None:
    response = client.post("/item", json=body)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_item_filters_and_pagination() -> None:
    first = create_item(10)
    second = create_item(20)
    third = create_item(30)

    response = client.get(
        "/item",
        params={"min_price": 15, "max_price": 30, "offset": 0, "limit": 2},
    )

    assert response.status_code == HTTPStatus.OK
    ids = [item["id"] for item in response.json()]
    assert first["id"] not in ids
    assert second["id"] in ids
    assert third["id"] in ids


def test_replace_item() -> None:
    item = create_item()
    response = client.put(
        f"/item/{item['id']}",
        json={"name": "Новое название", "price": 150},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": item["id"],
        "name": "Новое название",
        "price": 150.0,
        "deleted": False,
    }


def test_patch_item() -> None:
    item = create_item(70)
    response = client.patch(f"/item/{item['id']}", json={"price": 75.5})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == item["name"]
    assert response.json()["price"] == 75.5


@pytest.mark.parametrize(
    "body",
    [
        {"price": None},
        {"name": None},
        {"deleted": True},
        {"unknown": "value"},
    ],
)
def test_patch_item_validation(body: dict) -> None:
    item = create_item()
    response = client.patch(f"/item/{item['id']}", json=body)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_soft_delete_item() -> None:
    item = create_item()

    assert client.delete(f"/item/{item['id']}").status_code == HTTPStatus.OK
    assert client.get(f"/item/{item['id']}").status_code == HTTPStatus.NOT_FOUND

    visible = client.get("/item", params={"limit": 100}).json()
    with_deleted = client.get(
        "/item",
        params={"show_deleted": True, "limit": 100},
    ).json()
    assert item["id"] not in [stored["id"] for stored in visible]
    assert item["id"] in [stored["id"] for stored in with_deleted]


def test_create_empty_cart() -> None:
    response = client.post("/cart")

    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["location"].startswith("/cart/")

    cart = client.get(response.headers["location"]).json()
    assert cart["items"] == []
    assert cart["price"] == 0.0


def test_add_items_to_cart_and_calculate_total() -> None:
    item = create_item(12.50)
    cart_id = create_cart()

    client.post(f"/cart/{cart_id}/add/{item['id']}")
    response = client.post(f"/cart/{cart_id}/add/{item['id']}")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": cart_id,
        "items": [
            {
                "id": item["id"],
                "name": item["name"],
                "quantity": 2,
                "available": True,
            }
        ],
        "price": 25.0,
    }


def test_deleted_item_stays_in_cart_but_becomes_unavailable() -> None:
    item = create_item(30)
    cart_id = create_cart()
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    client.delete(f"/item/{item['id']}")
    cart = client.get(f"/cart/{cart_id}").json()

    assert cart["items"][0]["available"] is False
    assert cart["price"] == 30.0


def test_cart_filters() -> None:
    item = create_item(40)
    empty_cart = create_cart()
    filled_cart = create_cart()
    client.post(f"/cart/{filled_cart}/add/{item['id']}")

    min_result = client.get("/cart", params={"min_quantity": 1}).json()
    max_result = client.get("/cart", params={"max_quantity": 0}).json()

    assert filled_cart in [cart["id"] for cart in min_result]
    assert empty_cart in [cart["id"] for cart in max_result]


@pytest.mark.parametrize(
    "path",
    [
        "/item?offset=-1",
        "/item?limit=0",
        "/item?min_price=-1",
        "/cart?offset=-1",
        "/cart?limit=0",
        "/cart?min_quantity=-1",
    ],
)
def test_query_validation(path: str) -> None:
    assert client.get(path).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_missing_resources() -> None:
    missing = 999_999
    assert client.get(f"/item/{missing}").status_code == HTTPStatus.NOT_FOUND
    assert client.get(f"/cart/{missing}").status_code == HTTPStatus.NOT_FOUND
    assert (
        client.post(f"/cart/{missing}/add/{missing}").status_code
        == HTTPStatus.NOT_FOUND
    )


def test_data_survives_new_database_connection() -> None:
    item = create_item(88)
    engine.dispose()

    response = client.get(f"/item/{item['id']}")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == item


def test_data_survives_process_restart(tmp_path: Path) -> None:
    database = tmp_path / "persistent_shop.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database}"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    create_code = """
import json
from fastapi.testclient import TestClient
from shop_api.main import app

client = TestClient(app)
item = client.post('/item', json={'name': 'Книга', 'price': 450}).json()
print(json.dumps(item, ensure_ascii=False))
"""
    created = subprocess.run(
        [sys.executable, "-c", create_code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    item = json.loads(created.stdout)

    read_code = f"""
import json
from fastapi.testclient import TestClient
from shop_api.main import app

client = TestClient(app)
print(json.dumps(client.get('/item/{item["id"]}').json(), ensure_ascii=False))
"""
    read = subprocess.run(
        [sys.executable, "-c", read_code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert json.loads(read.stdout) == item


@pytest.mark.skipif(
    not os.environ["DATABASE_URL"].startswith("postgresql"),
    reason="Проверка блокировки строки требует PostgreSQL",
)
def test_parallel_cart_updates_do_not_lose_quantity() -> None:
    item = create_item(10)
    cart_id = create_cart()

    def add_once(_: int) -> int:
        with TestClient(app) as separate_client:
            return separate_client.post(f"/cart/{cart_id}/add/{item['id']}").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(add_once, range(20)))

    assert statuses == [HTTPStatus.OK] * 20
    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["quantity"] == 20
    assert cart["price"] == 200.0
