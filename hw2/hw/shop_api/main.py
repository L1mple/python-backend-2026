import os
from http import HTTPStatus

from fastapi import (
    FastAPI,
    HTTPException,
    Response,
)
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import (
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
)

from shop_api.chat import chat_router
from shop_api.models import (
    Cart,
    CreateOrReplaceItemRequest,
    Item,
    PartiallyUpdateItemRequest,
)
from shop_api.storage import DatabaseShopStorage

app = FastAPI(title="Shop API")
app.include_router(chat_router)
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/metrics", "/docs", "/openapi.json"],
).instrument(app).expose(app)

storage = DatabaseShopStorage(database_url=os.environ["DATABASE_URL"])


def _get_not_deleted_item_or_raise_404(
    item_id: int,
) -> Item:
    item = storage.get_item_by_id(item_id=item_id)
    if item is None or item.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    return item


def _get_cart_or_raise_404(
    cart_id: int,
) -> Cart:
    cart = storage.get_cart_by_id(cart_id=cart_id)
    if cart is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"cart {cart_id} not found",
        )
    return cart


@app.post(
    "/cart",
    status_code=HTTPStatus.CREATED,
)
def create_empty_cart(
    response: Response,
) -> dict[str, int]:
    new_cart_id = storage.create_empty_cart()
    response.headers["location"] = f"/cart/{new_cart_id}"
    return {"id": new_cart_id}


@app.get("/cart/{cart_id}")
def get_cart_by_id(
    cart_id: int,
) -> Cart:
    return _get_cart_or_raise_404(cart_id=cart_id)


@app.get("/cart")
def get_carts_page_filtered_by_price_and_quantity(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    min_quantity: NonNegativeInt | None = None,
    max_quantity: NonNegativeInt | None = None,
) -> list[Cart]:
    return storage.list_carts_page_filtered_by_price_and_quantity(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
    )


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> Cart:
    if not storage.cart_exists(cart_id=cart_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"cart {cart_id} not found",
        )
    _get_not_deleted_item_or_raise_404(item_id=item_id)
    storage.increase_item_quantity_in_cart_by_one(
        cart_id=cart_id,
        item_id=item_id,
    )
    return _get_cart_or_raise_404(cart_id=cart_id)


@app.post(
    "/item",
    status_code=HTTPStatus.CREATED,
)
def create_item(
    new_item_data: CreateOrReplaceItemRequest,
) -> Item:
    return storage.create_item(
        name=new_item_data.name,
        price=new_item_data.price,
    )


@app.get("/item/{item_id}")
def get_item_by_id(
    item_id: int,
) -> Item:
    return _get_not_deleted_item_or_raise_404(item_id=item_id)


@app.get("/item")
def get_items_page_filtered_by_price(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    show_deleted: bool = False,
) -> list[Item]:
    return storage.list_items_page_filtered_by_price(
        offset=offset,
        limit=limit,
        min_price=min_price,
        max_price=max_price,
        show_deleted=show_deleted,
    )


@app.put("/item/{item_id}")
def replace_item_by_id(
    item_id: int,
    replacement_item_data: CreateOrReplaceItemRequest,
) -> Item:
    replaced_item = storage.update_item_fields_by_id(
        item_id=item_id,
        changed_item_fields=replacement_item_data.model_dump(),
    )
    if replaced_item is None or replaced_item.deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    return replaced_item


@app.patch(
    "/item/{item_id}",
    response_model=Item,
)
def partially_update_item_by_id(
    item_id: int,
    changed_item_fields: PartiallyUpdateItemRequest,
) -> Item | Response:
    item = storage.update_item_fields_by_id(
        item_id=item_id,
        changed_item_fields=changed_item_fields.model_dump(exclude_unset=True),
    )
    if item is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)
    return item


@app.delete("/item/{item_id}")
def mark_item_as_deleted_by_id(
    item_id: int,
) -> Item:
    item = storage.mark_item_as_deleted_by_id(item_id=item_id)
    if item is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    return item
