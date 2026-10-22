from uuid import UUID, uuid4

import httpx
import pytest

from shop_api.database import connect
from shop_api.main import app


@pytest.fixture(autouse=True)
def empty_shop():
    with connect() as db:
        db.execute("TRUNCATE cart_items, carts, items RESTART IDENTITY")
    yield
    with connect() as db:
        db.execute("TRUNCATE cart_items, carts, items RESTART IDENTITY")


@pytest.mark.asyncio
async def test_item_cart_lifecycle_is_persistent():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post("/item", json={"name": "Milk", "price": 12.5})
        assert created.status_code == 201
        item_id = UUID(created.json()["id"])
        assert created.headers["location"] == f"/item/{item_id}"
        cart = await client.post("/cart")
        assert cart.status_code == 201
        cart_id = UUID(cart.json()["id"])
        url = f"/cart/{cart_id}/add/{item_id}"
        assert (await client.post(url)).json()["price"] == 12.5
        assert (await client.post(url)).json()["items"][0]["quantity"] == 2

        with connect() as db:
            row = db.execute(
                "SELECT quantity FROM cart_items WHERE cart_id = %s AND item_id = %s",
                (cart_id, item_id),
            ).fetchone()
            assert row["quantity"] == 2

        patched = await client.patch(f"/item/{item_id}", json={"name": "Oat milk", "price": 10})
        assert patched.status_code == 200
        cart_view = (await client.get(f"/cart/{cart_id}")).json()
        assert cart_view["price"] == 20
        assert cart_view["items"][0]["name"] == "Oat milk"
        assert (await client.delete(f"/item/{item_id}")).status_code == 200
        assert (await client.get(f"/item/{item_id}")).status_code == 404
        cart_view = (await client.get(f"/cart/{cart_id}")).json()
        assert cart_view["price"] == 0
        assert cart_view["items"][0]["available"] is False
        assert (await client.post(url)).status_code == 404


@pytest.mark.asyncio
async def test_filters_validation_and_missing_resources():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        low = (await client.post("/item", json={"name": "Low", "price": 5})).json()["id"]
        high = (await client.post("/item", json={"name": "High", "price": 20})).json()["id"]
        assert [item["id"] for item in (await client.get("/item", params={"min_price": 10})).json()] == [high]
        assert [item["id"] for item in (await client.get("/item", params={"max_price": 10})).json()] == [low]
        assert [item["id"] for item in (await client.get("/item", params={"show_deleted": True})).json()] == [low, high]
        assert (await client.get("/item", params={"limit": 0})).status_code == 422
        assert (await client.patch(f"/item/{low}", json={"price": None})).status_code == 422
        missing = uuid4()
        assert (await client.get(f"/cart/{missing}")).status_code == 404
        assert (await client.get(f"/item/{missing}")).status_code == 404
        assert (await client.put(f"/item/{missing}", json={"name": "X", "price": 1})).status_code == 404

        empty = (await client.post("/cart")).json()["id"]
        full = (await client.post("/cart")).json()["id"]
        await client.post(f"/cart/{full}/add/{high}")
        assert [cart["id"] for cart in (await client.get("/cart", params={"min_price": 1})).json()] == [full]
        assert [cart["id"] for cart in (await client.get("/cart", params={"max_quantity": 0})).json()] == [empty]
        assert [cart["id"] for cart in (await client.get("/cart", params={"offset": 1, "limit": 1})).json()] == [full]


@pytest.mark.asyncio
async def test_replacement_deletion_and_cart_order():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        first = (await client.post("/item", json={"name": "First", "price": 2})).json()["id"]
        second = (await client.post("/item", json={"name": "Second", "price": 3})).json()["id"]
        cart = (await client.post("/cart")).json()["id"]
        await client.post(f"/cart/{cart}/add/{second}")
        await client.post(f"/cart/{cart}/add/{first}")
        assert [item["id"] for item in (await client.get(f"/cart/{cart}")).json()["items"]] == [second, first]

        replaced = await client.put(f"/item/{first}", json={"name": "Replaced", "price": 4})
        assert replaced.status_code == 200
        assert replaced.json() == {"id": first, "name": "Replaced", "price": 4, "deleted": False}
        assert (await client.get(f"/cart/{cart}")).json()["price"] == 7
        assert (await client.put(f"/item/{first}", json={"price": 1})).status_code == 422
        await client.delete(f"/item/{first}")
        assert (await client.patch(f"/item/{first}", json={"name": "Ignored"})).status_code == 304
        assert (await client.put(f"/item/{first}", json={"name": "Ignored", "price": 1})).status_code == 404
        assert [item["id"] for item in (await client.get("/item")).json()] == [second]
        visible = (await client.get("/item", params={"show_deleted": True})).json()
        assert [item["id"] for item in visible] == [first, second]
        assert visible[0]["deleted"] is True


@pytest.mark.asyncio
async def test_get_item_and_empty_patch_preserve_stored_data():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        created = (await client.post("/item", json={"name": "Tea", "price": 8})).json()
        item_id = created["id"]

        fetched = await client.get(f"/item/{item_id}")
        assert fetched.status_code == 200
        assert fetched.json() == created

        patched = await client.patch(f"/item/{item_id}", json={})
        assert patched.status_code == 200
        assert patched.json() == created

        with connect() as db:
            row = db.execute(
                "SELECT name, price, deleted FROM items WHERE id = %s", (UUID(item_id),)
            ).fetchone()
        assert row == {"name": "Tea", "price": 8, "deleted": False}

