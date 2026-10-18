from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import NonNegativeFloat, NonNegativeInt, PositiveInt

from shop_api.contracts import (
    CartCreatedResponse,
    CartResponse,
    ItemPatchRequest,
    ItemRequest,
    ItemResponse,
)
from shop_api.store import store

router = APIRouter()


@router.post("/cart", status_code=HTTPStatus.CREATED)
async def post_cart(response: Response) -> CartCreatedResponse:
    cart_id = store.create_cart()
    response.headers["location"] = f"/cart/{cart_id}"

    return CartCreatedResponse(id=cart_id)


@router.get("/cart/{cart_id}")
async def get_cart(cart_id: int) -> CartResponse:
    view = store.get_cart(cart_id)

    if view is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Cart {cart_id} was not found")

    return CartResponse.from_view(view)


@router.get("/cart")
async def get_cart_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    min_quantity: Annotated[NonNegativeInt | None, Query()] = None,
    max_quantity: Annotated[NonNegativeInt | None, Query()] = None,
) -> list[CartResponse]:
    views = store.list_carts(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )

    return [CartResponse.from_view(view) for view in views]


@router.post("/cart/{cart_id}/add/{item_id}")
async def add_item_to_cart(cart_id: int, item_id: int) -> CartResponse:
    view = store.add_to_cart(cart_id, item_id)

    if view is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND,
            f"Cart {cart_id} or item {item_id} was not found",
        )

    return CartResponse.from_view(view)


@router.post("/item", status_code=HTTPStatus.CREATED)
async def post_item(body: ItemRequest, response: Response) -> ItemResponse:
    entity = store.create_item(body.name, body.price)
    response.headers["location"] = f"/item/{entity.id}"

    return ItemResponse.from_entity(entity)


@router.get("/item/{item_id}")
async def get_item(item_id: int) -> ItemResponse:
    entity = store.get_item(item_id)

    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")

    return ItemResponse.from_entity(entity)


@router.get("/item")
async def get_item_list(
    offset: Annotated[NonNegativeInt, Query()] = 0,
    limit: Annotated[PositiveInt, Query()] = 10,
    min_price: Annotated[NonNegativeFloat | None, Query()] = None,
    max_price: Annotated[NonNegativeFloat | None, Query()] = None,
    show_deleted: Annotated[bool, Query()] = False,
) -> list[ItemResponse]:
    entities = store.list_items(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )

    return [ItemResponse.from_entity(entity) for entity in entities]


@router.put("/item/{item_id}")
async def put_item(item_id: int, body: ItemRequest) -> ItemResponse:
    entity = store.replace_item(item_id, body.name, body.price)

    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")

    return ItemResponse.from_entity(entity)


@router.patch("/item/{item_id}")
async def patch_item(item_id: int, body: ItemPatchRequest) -> ItemResponse:
    entity = store.get_item(item_id, include_deleted=True)

    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")

    if entity.deleted:
        raise HTTPException(HTTPStatus.NOT_MODIFIED, f"Item {item_id} was not modified")

    updated = store.patch_item(item_id, name=body.name, price=body.price)

    if updated is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")

    return ItemResponse.from_entity(updated)


@router.delete("/item/{item_id}")
async def delete_item(item_id: int) -> ItemResponse:
    entity = store.delete_item(item_id)

    if entity is None:
        raise HTTPException(HTTPStatus.NOT_FOUND, f"Item {item_id} was not found")

    return ItemResponse.from_entity(entity)
