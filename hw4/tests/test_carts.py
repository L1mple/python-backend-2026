"""Тесты ресурса /cart: расчеты, ошибки, фильтры и параллельные добавления."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

MISSING_ID = 2_000_000_000


def test_post_cart_returns_location_and_empty_cart(client: TestClient) -> None:
    response = client.post("/cart")

    assert response.status_code == 201
    cart_id = response.json()["id"]
    assert response.headers["location"] == f"/cart/{cart_id}"
    assert client.get(f"/cart/{cart_id}").json() == {"id": cart_id, "items": [], "price": 0.0}


def test_get_missing_cart_is_404(client: TestClient) -> None:
    assert client.get(f"/cart/{MISSING_ID}").status_code == 404


def test_add_item_increases_quantity_and_price(client: TestClient, make_cart, make_item) -> None:
    cart_id = make_cart()
    item = make_item(name="Молоко", price=50.0)

    first = client.post(f"/cart/{cart_id}/add/{item['id']}")
    second = client.post(f"/cart/{cart_id}/add/{item['id']}")

    assert first.status_code == 200 and first.json()["items"][0]["quantity"] == 1
    assert second.json() == {
        "id": cart_id,
        "items": [{"id": item["id"], "name": "Молоко", "quantity": 2, "available": True}],
        "price": 100.0,
    }
    assert client.get(f"/cart/{cart_id}").json() == second.json()


def test_cart_price_sums_different_items(client: TestClient, make_cart, make_item) -> None:
    cart_id = make_cart()
    milk, bread = make_item(price=50.0), make_item(price=30.0)

    client.post(f"/cart/{cart_id}/add/{milk['id']}")
    client.post(f"/cart/{cart_id}/add/{milk['id']}")
    cart = client.post(f"/cart/{cart_id}/add/{bread['id']}").json()

    assert {i["id"]: i["quantity"] for i in cart["items"]} == {milk["id"]: 2, bread["id"]: 1}
    assert cart["price"] == 130.0


def test_add_to_missing_cart_is_404(client: TestClient, make_item) -> None:
    item = make_item()

    assert client.post(f"/cart/{MISSING_ID}/add/{item['id']}").status_code == 404


def test_add_missing_item_is_404(client: TestClient, make_cart) -> None:
    assert client.post(f"/cart/{make_cart()}/add/{MISSING_ID}").status_code == 404


def test_add_deleted_item_is_404(client: TestClient, make_cart, make_item) -> None:
    item = make_item()
    client.delete(f"/item/{item['id']}")

    assert client.post(f"/cart/{make_cart()}/add/{item['id']}").status_code == 404


def test_deleted_item_stays_in_cart_as_unavailable(client: TestClient, make_cart, make_item) -> None:
    cart_id = make_cart()
    item = make_item(price=20.0)
    client.post(f"/cart/{cart_id}/add/{item['id']}")

    client.delete(f"/item/{item['id']}")

    cart = client.get(f"/cart/{cart_id}").json()
    assert cart["items"][0]["available"] is False
    assert cart["price"] == 20.0


def test_cart_list_filters_by_price_and_quantity(client: TestClient, make_cart, make_item) -> None:
    # Товар с уникальной "огромной" ценой: другие тесты в такой диапазон не попадают
    item = make_item(price=7_777_777.0)
    one, three = make_cart(), make_cart()
    client.post(f"/cart/{one}/add/{item['id']}")
    for _ in range(3):
        client.post(f"/cart/{three}/add/{item['id']}")
    window = {"min_price": 7_777_777.0, "max_price": 3 * 7_777_777.0, "limit": 1000}

    def ids(**extra) -> set[int]:
        return {c["id"] for c in client.get("/cart", params={**window, **extra}).json()}

    assert {one, three} <= ids()
    assert one not in ids(min_price=7_777_778.0) and three in ids(min_price=7_777_778.0)
    assert three not in ids(max_price=7_777_778.0) and one in ids(max_price=7_777_778.0)
    assert one not in ids(min_quantity=2) and three in ids(min_quantity=2)
    assert three not in ids(max_quantity=2) and one in ids(max_quantity=2)


def test_cart_list_pagination_is_consistent(client: TestClient, make_cart) -> None:
    for _ in range(4):
        make_cart()
    full = client.get("/cart", params={"limit": 10_000}).json()

    page = client.get("/cart", params={"offset": 1, "limit": 2}).json()

    assert len(page) == 2
    assert page == full[1:3]


def test_parallel_adds_do_not_lose_updates(client: TestClient, make_cart, make_item) -> None:
    """20 одновременных запросов в одну корзину: благодаря блокировке строки корзины ничего не теряется."""
    cart_id = make_cart()
    item = make_item(price=1.0)

    with ThreadPoolExecutor(max_workers=10) as pool:
        statuses = list(pool.map(lambda _: client.post(f"/cart/{cart_id}/add/{item['id']}").status_code, range(20)))

    assert statuses == [200] * 20
    assert client.get(f"/cart/{cart_id}").json()["items"][0]["quantity"] == 20
