from http import HTTPStatus

import pytest


async def create_item(client, name="Book", price=10.0):
    response = await client.post("/item", json={"name": name, "price": price})
    assert response.status_code == HTTPStatus.CREATED
    return response


@pytest.mark.asyncio
async def test_item_crud_and_filters(client):
    response = await client.get("/item")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []

    response = await create_item(client)
    assert response.headers["location"] == "/item/1"
    assert response.json() == {
        "id": 1,
        "name": "Book",
        "price": 10.0,
        "deleted": False,
    }

    await create_item(client, name="Pen", price=2.5)

    response = await client.get("/item/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Book"

    response = await client.get("/item/999")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = await client.get(
        "/item",
        params={
            "offset": 0,
            "limit": 1,
            "min_price": 2,
            "max_price": 3,
            "show_deleted": True,
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert [item["name"] for item in response.json()] == ["Pen"]

    response = await client.put("/item/1", json={"name": "Notebook", "price": 15})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": 1,
        "name": "Notebook",
        "price": 15.0,
        "deleted": False,
    }

    response = await client.put("/item/999", json={"name": "None", "price": 1})
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = await client.patch("/item/1", json={})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Notebook"

    response = await client.patch("/item/1", json={"name": "Textbook"})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Textbook"

    response = await client.patch("/item/1", json={"price": 20})
    assert response.status_code == HTTPStatus.OK
    assert response.json()["price"] == 20.0

    response = await client.patch(
        "/item/1",
        json={"name": "Python book", "price": 25},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["name"] == "Python book"

    response = await client.patch("/item/999", json={})
    assert response.status_code == HTTPStatus.NOT_MODIFIED

    response = await client.patch("/item/999", json={"price": 1})
    assert response.status_code == HTTPStatus.NOT_MODIFIED

    response = await client.delete("/item/1")
    assert response.status_code == HTTPStatus.OK

    response = await client.get("/item/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = await client.get("/item")
    assert [item["id"] for item in response.json()] == [2]

    response = await client.get("/item", params={"show_deleted": True})
    assert [item["id"] for item in response.json()] == [1, 2]


@pytest.mark.asyncio
async def test_item_validation(client):
    response = await client.post(
        "/item",
        json={"name": "Book", "price": 10, "unexpected": True},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    response = await client.patch("/item/1", json={"unexpected": True})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    response = await client.get("/item", params={"offset": -1, "limit": 0})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_cart_flow_and_filters(client):
    response = await client.get("/cart")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == []

    response = await client.post("/cart")
    assert response.status_code == HTTPStatus.CREATED
    assert response.headers["location"] == "/cart/1"
    assert response.json() == {"id": 1, "items": [], "price": 0.0}

    await client.post("/cart")

    response = await client.get("/cart/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": 1, "items": [], "price": 0.0}

    response = await client.get("/cart/999")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = await client.post("/cart/1/add/999")
    assert response.status_code == HTTPStatus.NOT_FOUND

    await create_item(client, price=12.5)

    response = await client.post("/cart/999/add/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response = await client.post("/cart/1/add/1")
    assert response.status_code == HTTPStatus.OK
    response = await client.post("/cart/1/add/1")
    assert response.status_code == HTTPStatus.OK

    response = await client.get("/cart/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "id": 1,
        "items": [
            {"id": 1, "name": "Book", "quantity": 2, "available": True}
        ],
        "price": 25.0,
    }

    response = await client.get(
        "/cart",
        params={
            "offset": 0,
            "limit": 10,
            "min_price": 0,
            "max_price": 30,
            "min_quantity": 0,
            "max_quantity": 2,
        },
    )
    assert response.status_code == HTTPStatus.OK
    assert [cart["id"] for cart in response.json()] == [1, 2]
    assert response.json()[1]["items"] == []

    await client.delete("/item/1")

    response = await client.get("/cart/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"][0]["available"] is False

    response = await client.post("/cart/1/add/1")
    assert response.status_code == HTTPStatus.NOT_FOUND
