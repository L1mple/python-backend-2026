from http import HTTPStatus

from fastapi import (
    FastAPI,
    HTTPException,
    Response,
)
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
from shop_api.storage import InMemoryShopStorage

app = FastAPI(title="Shop API")
app.include_router(chat_router)

storage = InMemoryShopStorage()


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


def _raise_404_if_cart_does_not_exist(
    cart_id: int,
) -> None:
    if not storage.cart_exists(cart_id=cart_id):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"cart {cart_id} not found",
        )


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
    _raise_404_if_cart_does_not_exist(cart_id=cart_id)
    return storage.build_cart_with_current_prices(cart_id=cart_id)


@app.get("/cart")
def get_carts_page_filtered_by_price_and_quantity(
    offset: NonNegativeInt = 0,
    limit: PositiveInt = 10,
    min_price: NonNegativeFloat | None = None,
    max_price: NonNegativeFloat | None = None,
    min_quantity: NonNegativeInt | None = None,
    max_quantity: NonNegativeInt | None = None,
) -> list[Cart]:
    carts_matching_filters = []
    for cart in storage.build_all_carts_with_current_prices():
        total_quantity_of_items_in_cart = sum(item_in_cart.quantity for item_in_cart in cart.items)
        if min_price is not None and cart.price < min_price:
            continue
        if max_price is not None and cart.price > max_price:
            continue
        if min_quantity is not None and total_quantity_of_items_in_cart < min_quantity:
            continue
        if max_quantity is not None and total_quantity_of_items_in_cart > max_quantity:
            continue
        carts_matching_filters.append(cart)
    return carts_matching_filters[offset : offset + limit]


@app.post("/cart/{cart_id}/add/{item_id}")
def add_item_to_cart(
    cart_id: int,
    item_id: int,
) -> Cart:
    _raise_404_if_cart_does_not_exist(cart_id=cart_id)
    _get_not_deleted_item_or_raise_404(item_id=item_id)
    storage.increase_item_quantity_in_cart_by_one(
        cart_id=cart_id,
        item_id=item_id,
    )
    return storage.build_cart_with_current_prices(cart_id=cart_id)


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
    items_matching_filters = [
        item
        for item in storage.get_all_items_including_deleted()
        if (show_deleted or not item.deleted)
        and (min_price is None or item.price >= min_price)
        and (max_price is None or item.price <= max_price)
    ]
    return items_matching_filters[offset : offset + limit]


@app.put("/item/{item_id}")
def replace_item_by_id(
    item_id: int,
    replacement_item_data: CreateOrReplaceItemRequest,
) -> Item:
    item = _get_not_deleted_item_or_raise_404(item_id=item_id)
    item.name = replacement_item_data.name
    item.price = replacement_item_data.price
    return item


@app.patch(
    "/item/{item_id}",
    response_model=Item,
)
def partially_update_item_by_id(
    item_id: int,
    changed_item_fields: PartiallyUpdateItemRequest,
) -> Item | Response:
    item = storage.get_item_by_id(item_id=item_id)
    if item is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    if item.deleted:
        return Response(status_code=HTTPStatus.NOT_MODIFIED)

    for field_name, new_value in changed_item_fields.model_dump(exclude_unset=True).items():
        setattr(
            item,
            field_name,
            new_value,
        )
    return item


@app.delete("/item/{item_id}")
def mark_item_as_deleted_by_id(
    item_id: int,
) -> Item:
    item = storage.get_item_by_id(item_id=item_id)
    if item is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"item {item_id} not found",
        )
    item.deleted = True
    return item
